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
import { Link } from 'react-router-dom';
import type {
  ShadowTradesResponse,
  MetricsSummaryResponse,
  PaperAccountResponse,
  PaperPositionsResponse,
  MarketClockResponse,
  PortfolioHistoryResponse,
  PaperExposureResponse,
  CompareBooksResponse,
  ReconciliationResponse,
} from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { ManagedStatusBadge } from '../components/shared/ManagedStatusBadge';
import { ProtectionModeBadge } from '../components/shared/ProtectionModeBadge';
import { SourceBadge } from '../components/shared/SourceBadge';
import { IntelligenceBadge } from '../components/shared/IntelligenceBadge';
import { LifecycleStatusBadge } from '../components/shared/LifecycleStatusBadge';
import { SizingSummary } from '../components/shared/SizingSummary';
import { formatPnl, pnlClass, formatTs } from '../utils/format';

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
  const { data: paperExposure, isLoading: exposureLoading } = useQuery({
    queryKey: ['paperExposure'],
    queryFn: () => apiGet<PaperExposureResponse>(ENDPOINTS.paperExposure),
    refetchInterval: 15_000,
  });
  const { data: compareBooks } = useQuery({
    queryKey: ['compareBooks'],
    queryFn: () => apiGet<CompareBooksResponse>(ENDPOINTS.compareBooks),
    refetchInterval: 30_000,
  });
  const { data: reconciliation } = useQuery({
    queryKey: ['reconciliation'],
    queryFn: () => apiGet<ReconciliationResponse>(ENDPOINTS.systemReconciliation),
    refetchInterval: 30_000,
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
          <div className="grid-cards grid-cards--5">
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
          <p className="muted-text" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
            {positions.length} position(s) from broker. See lifecycle details below.
          </p>
        )}
      </section>
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
              <span className="empty-state__icon">📈</span>
              <p className="muted-text">No history data for this period</p>
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
        <SectionHeader 
          title="Paper Exposure & Lifecycle" 
          subtitle="Complete lifecycle detail — canonical view for all position inspection. This is the authoritative source for stop, target, protection, sizing, and managed status." 
        />
        {exposureLoading && <LoadingSkeleton lines={4} />}
        {!exposureLoading && (!paperExposure?.positions || paperExposure.positions.length === 0) ? (
          <EmptyState message="No open paper positions with lifecycle data." icon="📊" />
        ) : !exposureLoading && paperExposure?.positions ? (
          <>
            {paperExposure.positions.some((p) => p.orphaned || p.managed_status === 'orphaned' || p.managed_status === 'unmanaged') && (
              <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
                <strong>⚠ Critical:</strong> {paperExposure.positions.filter(p => p.orphaned || p.managed_status === 'orphaned' || p.managed_status === 'unmanaged').length} position(s) are unmanaged or orphaned. Review exit plans and protection status below.
              </div>
            )}
            {paperExposure.positions.some((p) => p.static_fallback_at_entry) && (
              <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-warning)', backgroundColor: 'var(--color-warning-bg, #2d2b1b)' }}>
                <strong>⚠ Warning:</strong> {paperExposure.positions.filter(p => p.static_fallback_at_entry).length} position(s) were opened using static fallback symbols.
              </div>
            )}
            {paperExposure.positions.some((p) => !p.protection_active && p.managed_status !== 'exited') && (
              <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-warning)', backgroundColor: 'var(--color-warning-bg, #2d2b1b)' }}>
                <strong>⚠ Warning:</strong> {paperExposure.positions.filter(p => !p.protection_active && p.managed_status !== 'exited').length} position(s) have no active protection.
              </div>
            )}
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Entry Price</th>
                    <th>Current Price</th>
                    <th>Market Value</th>
                    <th>Unrealized P&L</th>
                    <th>P&L %</th>
                    <th>Source</th>
                    <th>Strategy</th>
                    <th>Managed</th>
                    <th>Stop</th>
                    <th>Target</th>
                    <th>Force-Flat</th>
                    <th>Protection</th>
                    <th>Intelligence</th>
                    <th>Sizing</th>
                    <th>Entry</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {paperExposure.positions.map((pos) => (
                    <tr key={`${pos.symbol}-${pos.side}`}>
                      <td className="cell--symbol">{pos.symbol}</td>
                      <td>
                        <span className={pos.side?.toLowerCase() === 'long' ? 'signal-side signal-side--buy' : 'signal-side signal-side--sell'}>
                          {pos.side?.toUpperCase()}
                        </span>
                      </td>
                      <td>{pos.qty}</td>
                      <td>{pos.avg_entry_price != null ? formatMoney(pos.avg_entry_price) : '—'}</td>
                      <td>{pos.current_price != null ? formatMoney(pos.current_price) : '—'}</td>
                      <td>{pos.market_value != null ? formatMoney(pos.market_value) : '—'}</td>
                      <td className={pos.unrealized_pl != null ? pnlClass(pos.unrealized_pl) : ''}>
                        {pos.unrealized_pl != null ? formatPnl(pos.unrealized_pl) : '—'}
                      </td>
                      <td className={pos.unrealized_plpc != null ? pnlClass(pos.unrealized_plpc) : ''}>
                        {pos.unrealized_plpc != null ? `${pos.unrealized_plpc >= 0 ? '+' : ''}${pos.unrealized_plpc.toFixed(2)}%` : '—'}
                      </td>
                      <td><SourceBadge source={pos.source} /></td>
                      <td>
                        {pos.strategy_id ? (
                          <span className="muted-text" style={{ fontSize: '0.85rem' }}>
                            {pos.strategy_id}
                            {pos.strategy_version && ` v${pos.strategy_version}`}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td><ManagedStatusBadge status={pos.managed_status} /></td>
                      <td>{pos.stop_price != null ? `$${Number(pos.stop_price).toFixed(2)}` : '—'}</td>
                      <td>{pos.target_price != null ? `$${Number(pos.target_price).toFixed(2)}` : '—'}</td>
                      <td>{pos.force_flat_time ?? '—'}</td>
                      <td>
                        <ProtectionModeBadge mode={pos.protection_mode} active={pos.protection_active} />
                      </td>
                      <td>
                        <IntelligenceBadge
                          scrappy={pos.scrappy_at_entry ? { present: true, stale: pos.scrappy_detail?.stale_flag, conflict: pos.scrappy_detail?.conflict_flag } : false}
                          aiReferee={pos.ai_referee_at_entry ? { ran: pos.ai_referee_detail?.ran } : false}
                          compact
                        />
                      </td>
                      <td><SizingSummary sizing={pos.sizing_at_entry} compact /></td>
                      <td className="cell--ts">{pos.entry_ts ? formatTs(pos.entry_ts) : '—'}</td>
                      <td>
                        {pos.signal_uuid && (
                          <Link to={`/signals/${pos.signal_uuid}`} className="link-mono" style={{ fontSize: '0.85rem' }}>
                            Signal
                          </Link>
                        )}
                        {pos.entry_order_id && (
                          <span className="muted-text" style={{ fontSize: '0.75rem', display: 'block' }}>
                            Entry: {pos.entry_order_id.slice(0, 12)}…
                          </span>
                        )}
                        {pos.exit_order_id && (
                          <span className="muted-text" style={{ fontSize: '0.75rem', display: 'block' }}>
                            Exit: {pos.exit_order_id.slice(0, 12)}…
                          </span>
                        )}
                        {pos.lifecycle_status && (
                          <LifecycleStatusBadge status={pos.lifecycle_status} />
                        )}
                        {pos.static_fallback_at_entry && (
                          <span className="flag-badge flag-badge--warn" style={{ fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                            Static fallback
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </section>

      {compareBooks && (
        <section>
          <SectionHeader title="Compare Books" subtitle="Paper vs shadow summary" />
          <div className="grid-cards grid-cards--4">
            <KPICard
              title="Shadow trades"
              value={compareBooks.shadow?.trade_count ?? 0}
              variant="shadow"
            />
            <KPICard
              title="Shadow P&L"
              value={compareBooks.shadow?.total_net_pnl != null ? formatPnl(compareBooks.shadow.total_net_pnl) : '—'}
              variant="shadow"
              valueClass={pnlClass(compareBooks.shadow?.total_net_pnl)}
            />
            <KPICard
              title="Paper fills"
              value={compareBooks.paper?.fill_count ?? 0}
            />
            <KPICard
              title="Paper P&L"
              value={compareBooks.paper?.total_net_pnl != null ? formatPnl(compareBooks.paper.total_net_pnl) : '—'}
              valueClass={pnlClass(compareBooks.paper?.total_net_pnl ?? null)}
            />
          </div>
          {compareBooks.note && (
            <p className="muted-text" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
              {compareBooks.note}
            </p>
          )}
        </section>
      )}

      {reconciliation && (
        <section>
          <SectionHeader title="Reconciliation" subtitle="Latest reconciliation run status" />
          <div className="grid-cards grid-cards--5">
            <KPICard
              title="Status"
              value={reconciliation.status ?? '—'}
            />
            <KPICard
              title="Orders matched"
              value={reconciliation.orders_matched ?? 0}
            />
            <KPICard
              title="Orders mismatch"
              value={reconciliation.orders_mismatch ?? 0}
            />
            <KPICard
              title="Positions matched"
              value={reconciliation.positions_matched ?? 0}
            />
            <KPICard
              title="Positions mismatch"
              value={reconciliation.positions_mismatch ?? 0}
            />
          </div>
          {reconciliation.run_at && (
            <p className="muted-text" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
              Last run: {formatTs(reconciliation.run_at)}
            </p>
          )}
        </section>
      )}

      <section>
        <SectionHeader title="Shadow Book" subtitle="Internal fill ledger — shadow trades only" />
        {!shadowTrades && !metrics ? (
          <BackendNotConnected message="Could not load shadow data from API" detail={apiErrorDetail} />
        ) : (
          <div className="grid-cards grid-cards--3">
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
