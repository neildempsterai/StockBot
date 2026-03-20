import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { ShadowTradesResponse } from '../types/api';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { RefreshBadge } from '../components/shared/RefreshBadge';
import { EmptyState } from '../components/shared/EmptyState';
import { SectionHeader } from '../components/shared/SectionHeader';
import { formatTs, formatPnl, formatPrice, pnlClass, shortUuid } from '../utils/format';

export function ShadowTrades() {
  const { data, isLoading, isError, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['shadowTrades'],
    queryFn: () => apiGet<ShadowTradesResponse>(`${ENDPOINTS.shadowTrades}?limit=50`),
    refetchInterval: 15_000,
  });

  if (isLoading) {
    return (
      <div>
        <h1 className="page-title">Shadow Trades</h1>
        <LoadingSkeleton lines={8} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div>
        <h1 className="page-title">Shadow Trades</h1>
        <BackendNotConnected message="Could not load shadow trades from API" />
      </div>
    );
  }

  const { trades, count } = data;
  const totalNetPnl = trades.reduce((sum, t) => sum + (t.net_pnl ?? 0), 0);
  const totalGrossPnl = trades.reduce((sum, t) => sum + (t.gross_pnl ?? 0), 0);
  const winners = trades.filter((t) => (t.net_pnl ?? 0) > 0).length;
  const losers = trades.filter((t) => (t.net_pnl ?? 0) < 0).length;

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">Shadow Trades</h1>
        <RefreshBadge dataUpdatedAt={dataUpdatedAt} isFetching={isFetching} intervalSec={15} />
      </div>

      {count !== undefined && count > 0 && (
        <div className="grid-cards grid-cards--4">
          <div className="kpi-card kpi-card--shadow">
            <div className="kpi-card__title">Total trades</div>
            <div className="kpi-card__value">{count}</div>
          </div>
          <div className="kpi-card kpi-card--shadow">
            <div className="kpi-card__title">Net P&amp;L</div>
            <div className={`kpi-card__value ${pnlClass(totalNetPnl)}`}>{formatPnl(totalNetPnl)}</div>
          </div>
          <div className="kpi-card kpi-card--shadow">
            <div className="kpi-card__title">Gross P&amp;L</div>
            <div className={`kpi-card__value ${pnlClass(totalGrossPnl)}`}>{formatPnl(totalGrossPnl)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-card__title">Winners / Losers</div>
            <div className="kpi-card__value">
              <span className="pnl--positive">{winners}W</span>
              {' / '}
              <span className="pnl--negative">{losers}L</span>
            </div>
          </div>
        </div>
      )}

      <SectionHeader
        title={`${count ?? 0} trade${(count ?? 0) !== 1 ? 's' : ''}`}
        subtitle="Most recent 50 — auto-refreshes every 15s"
      />

      {!trades?.length ? (
        <EmptyState message="No shadow trades yet." icon="👻" />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Signal UUID</th>
                <th>Mode</th>
                <th>Strategy</th>
                <th>Type</th>
                <th>Entry time</th>
                <th>Exit time</th>
                <th>Entry $</th>
                <th>Exit $</th>
                <th>Qty</th>
                <th>Gross P&amp;L</th>
                <th>Net P&amp;L</th>
                <th>Exit reason</th>
                <th>Scrappy</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.signal_uuid}>
                  <td className="cell--mono cell--muted">{shortUuid(t.signal_uuid)}</td>
                  <td>{t.execution_mode}</td>
                  <td className="cell--small">
                    {t.strategy_id ? (
                      <div>
                        <div>{t.strategy_id}</div>
                        {t.strategy_version && (
                          <div className="muted-text" style={{ fontSize: '0.75rem' }}>v{t.strategy_version}</div>
                        )}
                      </div>
                    ) : '—'}
                  </td>
                  <td>
                    <span className={t.strategy_id?.includes('SWING') ? 'badge badge--swing' : 'badge badge--intraday'}>
                      {t.strategy_id?.includes('SWING') ? 'Swing' : 'Intraday'}
                    </span>
                  </td>
                  <td className="cell--ts" title={t.entry_ts ?? ''}>{formatTs(t.entry_ts)}</td>
                  <td className="cell--ts" title={t.exit_ts ?? ''}>{formatTs(t.exit_ts)}</td>
                  <td>{formatPrice(t.entry_price)}</td>
                  <td>{formatPrice(t.exit_price)}</td>
                  <td>{t.qty ?? '—'}</td>
                  <td className={pnlClass(t.gross_pnl)}>{formatPnl(t.gross_pnl)}</td>
                  <td className={`cell--pnl ${pnlClass(t.net_pnl)}`}>{formatPnl(t.net_pnl)}</td>
                  <td className="cell--muted cell--small">{t.exit_reason ?? '—'}</td>
                  <td>
                    {t.scrappy_mode ? (
                      <span className="scrappy-badge">{t.scrappy_mode}</span>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
