import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { ShadowTradesResponse, StrategiesResponse } from '../types/api';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { RefreshBadge } from '../components/shared/RefreshBadge';
import { EmptyState } from '../components/shared/EmptyState';
import { SectionHeader } from '../components/shared/SectionHeader';
import { formatTs, formatPnl, formatPrice, pnlClass, shortUuid } from '../utils/format';

export function ShadowTrades() {
  const [strategyFilter, setStrategyFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');

  const { data, isLoading, isError, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['shadowTrades'],
    queryFn: () => apiGet<ShadowTradesResponse>(`${ENDPOINTS.shadowTrades}?limit=50`),
    refetchInterval: 15_000,
  });

  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiGet<StrategiesResponse>(ENDPOINTS.strategies),
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

  const strategyIds = [...new Set([
    ...(strategies?.strategies?.map(s => s.strategy_id) ?? []),
    ...(data.trades?.map(t => t.strategy_id).filter((id): id is string => !!id) ?? []),
  ])];

  const filteredTrades = data.trades.filter(t => {
    if (strategyFilter !== 'all' && t.strategy_id !== strategyFilter) return false;
    if (typeFilter === 'swing' && !t.strategy_id?.includes('SWING')) return false;
    if (typeFilter === 'intraday' && t.strategy_id?.includes('SWING')) return false;
    return true;
  });

  const { count } = data;
  const totalNetPnl = filteredTrades.reduce((sum, t) => sum + (t.net_pnl ?? 0), 0);
  const totalGrossPnl = filteredTrades.reduce((sum, t) => sum + (t.gross_pnl ?? 0), 0);
  const winners = filteredTrades.filter((t) => (t.net_pnl ?? 0) > 0).length;
  const losers = filteredTrades.filter((t) => (t.net_pnl ?? 0) < 0).length;

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">Shadow Trades</h1>
        <RefreshBadge dataUpdatedAt={dataUpdatedAt} isFetching={isFetching} intervalSec={15} />
      </div>

      <div className="grid-cards grid-cards--4">
        <div className="kpi-card kpi-card--shadow">
          <div className="kpi-card__title">Total Trades</div>
          <div className="kpi-card__value">{count ?? filteredTrades.length}</div>
          {strategyFilter !== 'all' && <div className="kpi-card__subtitle muted-text">Showing {filteredTrades.length}</div>}
        </div>
        <div className="kpi-card kpi-card--shadow">
          <div className="kpi-card__title">Net P&L</div>
          <div className={`kpi-card__value ${pnlClass(totalNetPnl)}`}>{formatPnl(totalNetPnl)}</div>
        </div>
        <div className="kpi-card kpi-card--shadow">
          <div className="kpi-card__title">Gross P&L</div>
          <div className={`kpi-card__value ${pnlClass(totalGrossPnl)}`}>{formatPnl(totalGrossPnl)}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card__title">Winners / Losers</div>
          <div className="kpi-card__value">
            <span className="pnl--positive">{winners}W</span>
            {' / '}
            <span className="pnl--negative">{losers}L</span>
          </div>
          {filteredTrades.length > 0 && (
            <div className="kpi-card__subtitle muted-text">
              {(winners / filteredTrades.length * 100).toFixed(0)}% win rate
            </div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="filter-row">
        <span className="filter-label">Strategy:</span>
        <button
          className={`filter-btn${strategyFilter === 'all' ? ' filter-btn--active' : ''}`}
          onClick={() => setStrategyFilter('all')}
        >
          All
        </button>
        {strategyIds.map(id => (
          <button
            key={id}
            className={`filter-btn${strategyFilter === id ? ' filter-btn--active' : ''}`}
            onClick={() => setStrategyFilter(id)}
          >
            {id}
          </button>
        ))}
        <span style={{ width: '1rem' }} />
        <span className="filter-label">Type:</span>
        <button
          className={`filter-btn${typeFilter === 'all' ? ' filter-btn--active' : ''}`}
          onClick={() => setTypeFilter('all')}
        >
          All
        </button>
        <button
          className={`filter-btn${typeFilter === 'intraday' ? ' filter-btn--active' : ''}`}
          onClick={() => setTypeFilter('intraday')}
        >
          Intraday
        </button>
        <button
          className={`filter-btn${typeFilter === 'swing' ? ' filter-btn--active' : ''}`}
          onClick={() => setTypeFilter('swing')}
        >
          Swing
        </button>
      </div>

      <SectionHeader
        title={`${filteredTrades.length} trade${filteredTrades.length !== 1 ? 's' : ''}`}
        subtitle="Most recent 50 — auto-refreshes every 15s"
      />

      {!filteredTrades?.length ? (
        <EmptyState message={strategyFilter !== 'all' ? `No shadow trades for ${strategyFilter}` : 'No shadow trades yet.'} icon="👻" />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Signal</th>
                <th>Mode</th>
                <th>Strategy</th>
                <th>Type</th>
                <th>Entry</th>
                <th>Exit</th>
                <th>Entry $</th>
                <th>Exit $</th>
                <th>Qty</th>
                <th>Gross P&L</th>
                <th>Net P&L</th>
                <th>Exit Reason</th>
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((t) => (
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
