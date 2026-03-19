import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type {
  ShadowTradesResponse,
  MetricsSummaryResponse,
  PaperAccountResponse,
  PaperPositionsResponse,
  MarketClockResponse,
  PortfolioHistoryResponse,
} from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { SectionHeader } from '../components/shared/SectionHeader';
import { formatPnl, pnlClass } from '../utils/format';

type HistoryPeriod = '1D' | '1W' | '1M' | '3M' | '1A';
type HistoryTimeframe = '5Min' | '15Min' | '1H' | '1D';

const PERIOD_OPTIONS: { label: string; value: HistoryPeriod; tf: HistoryTimeframe }[] = [
  { label: '1D', value: '1D', tf: '5Min' },
  { label: '1W', value: '1W', tf: '15Min' },
  { label: '1M', value: '1M', tf: '1H' },
  { label: '3M', value: '3M', tf: '1D' },
  { label: '1Y', value: '1A', tf: '1D' },
];

interface ChartPoint { ts: number; label: string; equity: number; pl: number; }

function formatChartTs(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function buildChartData(history: PortfolioHistoryResponse): ChartPoint[] {
  const timestamps = history.timestamp ?? [];
  const equity = history.equity ?? [];
  const pl = history.profit_loss ?? [];
  return timestamps.map((ts, i) => ({
    ts,
    label: formatChartTs(ts),
    equity: equity[i] ?? 0,
    pl: pl[i] ?? 0,
  }));
}

function formatMoney(s: string | number | undefined): string {
  if (s == null || s === '') return '\u2014';
  const n = typeof s === 'number' ? s : parseFloat(s as string);
  if (Number.isNaN(n)) return String(s);
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(n);
}

export function Portfolio() {
  const [period, setPeriod] = useState<{ value: HistoryPeriod; tf: HistoryTimeframe }>(PERIOD_OPTIONS[0]);
  const { data: shadowTrades, isLoading: tradesLoading, error: tradesError } = useQuery({
    queryKey: ['shadowTrades'],
    queryFn: () => apiGet<ShadowTradesResponse>(`${ENDPOINTS.shadowTrades}?limit=50`),
    refetchInterval: 30_000,
  });
  const { data: metrics, error: metricsError } = useQuery({
    queryKey: ['metricsSummary'],
    queryFn: () => apiGet<MetricsSummaryResponse>(ENDPOINTS.metricsSummary),
    refetchInterval: 30_000,
  });

  const {
    data: account,
    isLoading: accountLoading,
    error: accountError,
  } = useQuery({
    queryKey: ['paperAccount'],
    queryFn: () => apiGet<PaperAccountResponse>(ENDPOINTS.account),
    refetchInterval: 30_000,
    retry: false,
  });
  const { data: positionsData } = useQuery({
    queryKey: ['paperPositions'],
    queryFn: () => apiGet<PaperPositionsResponse>(ENDPOINTS.positions),
    refetchInterval: 30_000,
    enabled: !!account,
    retry: false,
  });
  const { data: clock } = useQuery({
    queryKey: ['marketClock'],
    queryFn: () => apiGet<MarketClockResponse>(ENDPOINTS.clock),
    refetchInterval: 60_000,
    enabled: !!account,
    retry: false,
  });
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['portfolioHistory', period.value, period.tf],
    queryFn: () =>
      apiGet<PortfolioHistoryResponse>(ENDPOINTS.portfolioHistory, {
        period: period.value,
        timeframe: period.tf,
      }),
    refetchInterval: 60_000,
    enabled: !!account,
    retry: false,
  });

  const err = tradesError || metricsError;
  const apiErrorDetail = err && typeof err === 'object' && 'detail' in err
    ? String((err as { detail?: string }).detail)
    : undefined;
  const paperErrorDetail = accountError && typeof accountError === 'object' && 'detail' in accountError
    ? String((accountError as { detail?: string }).detail)
    : undefined;

  const paperUnconfigured = accountError != null && paperErrorDetail?.toLowerCase().includes('not configured');

  if (tradesLoading) {
    return (
      <div>
        <h1 className="page-title">Portfolio</h1>
        <LoadingSkeleton lines={4} />
      </div>
    );
  }

  const pnl = metrics?.total_net_pnl_shadow ?? null;
  const positions = positionsData?.positions ?? [];
  const chartData = history ? buildChartData(history) : [];
  const latestEquity = chartData.length > 0 ? chartData[chartData.length - 1].equity : null;
  const firstEquity = chartData.length > 0 ? chartData[0].equity : null;
  const equityChange = latestEquity != null && firstEquity != null ? latestEquity - firstEquity : null;

  return (
    <div className="page-stack">
      <h1 className="page-title">Portfolio</h1>
      <section>
        <SectionHeader title="Paper Account" subtitle="Broker-connected paper trading (Alpaca)" />
        {accountLoading && !account ? (
          <LoadingSkeleton lines={2} />
        ) : paperUnconfigured ? (
          <BackendNotConnected
            message="Alpaca paper account not configured"
            detail={paperErrorDetail ?? 'Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY to enable.'}
          />
        ) : accountError && !paperUnconfigured ? (
          <BackendNotConnected message="Could not load paper account" detail={paperErrorDetail} />
        ) : account ? (
          <div className="grid-cards">
            <KPICard title="Equity" value={formatMoney(account.equity)} variant="default" />
            <KPICard title="Cash" value={formatMoney(account.cash)} variant="default" />
            <KPICard title="Buying power" value={formatMoney(account.buying_power)} variant="default" />
            <KPICard title="Open positions" value={positions.length} variant="default" />
            {clock && (
              <KPICard
                title="Market"
                value={clock.is_open ? 'Open' : 'Closed'}
                variant="default"
              />
            )}
          </div>
        ) : null}
        {account && positions.length > 0 && (
          <div className="table-wrap" style={{ marginTop: '1rem' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Qty</th>
                  <th>Market value</th>
                  <th>Unrealized P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.symbol}>
                    <td className="cell--symbol">{p.symbol}</td>
                    <td>{p.qty ?? '\u2014'}</td>
                    <td>{formatMoney(p.market_value)}</td>
                    <td className={pnlClass(p.unrealized_pl ? parseFloat(p.unrealized_pl) : null)}>
                      {formatMoney(p.unrealized_pl)}
                      {p.unrealized_plpc != null ? ` (${(parseFloat(p.unrealized_plpc) * 100).toFixed(2)}%)` : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {/* ── Portfolio History Chart ────────────────────── */}
      {account && !paperUnconfigured && (
        <section>
          <SectionHeader title="Equity Curve" subtitle="Portfolio value over time" />
          <div className="filter-row" style={{ marginBottom: '0.75rem' }}>
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                className={`filter-btn${period.value === opt.value ? ' filter-btn--active' : ''}`}
                onClick={() => setPeriod(opt)}
              >
                {opt.label}
              </button>
            ))}
            {equityChange != null && (
              <span className={`filter-count ${pnlClass(equityChange)}`}>
                {equityChange >= 0 ? '+' : ''}{formatMoney(equityChange)}
              </span>
            )}
          </div>
          {historyLoading ? (
            <LoadingSkeleton lines={4} />
          ) : chartData.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon">📈</div>
              <div className="empty-state__msg">No history data for this period</div>
            </div>
          ) : (
            <div className="chart-container" style={{ height: 240 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00e5ff" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#00e5ff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e2a35" />
                  <XAxis dataKey="label" tick={{ fill: '#8899aa', fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis
                    tick={{ fill: '#8899aa', fontSize: 11 }}
                    tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`}
                    width={52}
                  />
                  <Tooltip
                    contentStyle={{ background: '#0d1117', border: '1px solid #1e2a35', color: '#c9d1d9' }}
                    formatter={(v) => [formatMoney(v as number), 'Equity']}
                    labelStyle={{ color: '#8899aa' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="equity"
                    stroke="#00e5ff"
                    strokeWidth={2}
                    fill="url(#equityGrad)"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      )}

      <section>
        <SectionHeader title="Shadow Book" subtitle="Internal fill ledger — shadow trades only" />
        {!shadowTrades && !metrics ? (
          <BackendNotConnected message="Could not load shadow data from API" detail={apiErrorDetail} />
        ) : (
          <div className="grid-cards">
            <KPICard
              title="Shadow trades"
              value={metrics?.shadow_trades_total ?? shadowTrades?.count ?? 0}
              variant="shadow"
            />
            <KPICard
              title="Net P&L (shadow)"
              value={pnl != null ? formatPnl(pnl) : '\u2014'}
              variant="shadow"
              valueClass={pnlClass(pnl)}
            />
          </div>
        )}
      </section>
    </div>
  );
}
