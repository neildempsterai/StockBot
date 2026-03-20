import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { EmptyState } from '../components/shared/EmptyState';
import { SectionHeader } from '../components/shared/SectionHeader';
import { StateBadge } from '../components/shared/StateBadge';
import { IntelligenceBadge } from '../components/shared/IntelligenceBadge';
import { formatTs, formatPrice } from '../utils/format';
import type { PaperExposureResponse } from '../types/api';

interface SignalRow {
  signal_uuid: string;
  symbol?: string;
  side?: string;
  qty?: number;
  quote_ts?: string;
  strategy_id?: string;
  strategy_version?: string;
  reason_codes?: string[];
  paper_order_id?: string;
  execution_mode?: string;
  scrappy_mode?: string;
  opportunity_candidate_rank?: number;
  opportunity_candidate_source?: string;
  opportunity_market_score?: number;
  opportunity_semantic_score?: number;
  intelligence_snapshot_id?: number;
  ai_referee_assessment_id?: number;
  bid?: number;
  ask?: number;
  last?: number;
  spread_bps?: number;
}

export function LiveSignalFeed() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['signals'],
    queryFn: () => apiGet<{ signals?: SignalRow[] }>(`${ENDPOINTS.signals}?limit=50`),
    refetchInterval: 15_000,
  });
  const { data: paperExposure } = useQuery({
    queryKey: ['paperExposure'],
    queryFn: () => apiGet<PaperExposureResponse>(ENDPOINTS.paperExposure),
    refetchInterval: 15_000,
  });
  
  // Create a set of signal UUIDs that have open paper positions
  const openPaperSignalUuids = new Set(
    paperExposure?.positions?.filter(p => p.signal_uuid).map(p => p.signal_uuid) ?? []
  );

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Live Signals</h1>
        <LoadingSkeleton lines={8} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Live Signals</h1>
        <BackendNotConnected message="Could not load signals" />
      </div>
    );
  }

  const signals = data?.signals ?? [];

  return (
    <div className="page-stack">
      <h1 className="page-title">Live Signals</h1>
      <SectionHeader title="Recent signals" subtitle="Strategy-generated signals (deterministic authority)" />
      {signals.length === 0 ? (
        <EmptyState 
          message="No deterministic strategy signals yet" 
          detail="This page shows only actual strategy-generated trade signals. An empty state here is normal if the strategy has not triggered any signals. Focus symbols and premarket prep appear on other pages."
          icon="⚡" 
        />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Time</th>
                <th>Strategy</th>
                <th>Opportunity</th>
                <th>Intelligence</th>
                <th>Reasons</th>
                <th>Price</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s) => {
                const hasOpenPosition = openPaperSignalUuids.has(s.signal_uuid);
                const hasPaperOrder = !!s.paper_order_id;
                const executionMode = s.execution_mode || 'shadow';
                return (
                  <tr 
                    key={s.signal_uuid}
                    style={hasOpenPosition ? { backgroundColor: 'var(--color-success-bg, rgba(63, 185, 80, 0.1))' } : undefined}
                  >
                    <td className="cell--symbol">{s.symbol}</td>
                    <td>
                      <span className={s.side?.toLowerCase() === 'buy' ? 'signal-side signal-side--buy' : 'signal-side signal-side--sell'}>
                        {s.side?.toUpperCase()}
                      </span>
                    </td>
                    <td>{s.qty}</td>
                    <td className="cell--ts">{formatTs(s.quote_ts)}</td>
                    <td>
                      <div>{s.strategy_id ?? '—'}</div>
                      {s.strategy_version && (
                        <div className="muted-text" style={{ fontSize: '0.75rem' }}>v{s.strategy_version}</div>
                      )}
                    </td>
                    <td className="cell--muted cell--small">
                      {s.opportunity_candidate_rank ? (
                        <div>
                          <div>Rank: {s.opportunity_candidate_rank}</div>
                          {s.opportunity_candidate_source && (
                            <div style={{ fontSize: '0.7rem', marginTop: '0.25rem' }}>
                              {s.opportunity_candidate_source}
                            </div>
                          )}
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <IntelligenceBadge
                        scrappy={s.intelligence_snapshot_id ? { present: true } : false}
                        aiReferee={s.ai_referee_assessment_id ? { ran: true } : false}
                        compact
                      />
                      {s.scrappy_mode && (
                        <div className="muted-text" style={{ fontSize: '0.7rem', marginTop: '0.25rem' }}>
                          {s.scrappy_mode}
                        </div>
                      )}
                    </td>
                    <td className="cell--muted cell--small">
                      {(s.reason_codes ?? []).length > 0 ? (
                        <div>
                          {(s.reason_codes ?? []).slice(0, 3).join(', ')}
                          {(s.reason_codes ?? []).length > 3 && (
                            <span className="muted-text" style={{ fontSize: '0.7rem' }}>
                              {' '}+{(s.reason_codes ?? []).length - 3} more
                            </span>
                          )}
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="cell--muted cell--small">
                      {s.last ? (
                        <div>
                          <div>{formatPrice(s.last)}</div>
                          {s.spread_bps != null && (
                            <div style={{ fontSize: '0.7rem' }}>
                              {s.spread_bps > 0 ? '+' : ''}{(s.spread_bps / 100).toFixed(2)}%
                            </div>
                          )}
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <div>
                        {hasOpenPosition && (
                          <StateBadge label="Open Position" variant="success" />
                        )}
                        {!hasOpenPosition && hasPaperOrder && (
                          <StateBadge label="Order Filled" variant="default" />
                        )}
                        {!hasOpenPosition && !hasPaperOrder && (
                          <span className="muted-text">—</span>
                        )}
                      </div>
                      <div style={{ marginTop: '0.25rem' }}>
                        <span className="muted-text" style={{ fontSize: '0.7rem' }}>
                          {executionMode}
                        </span>
                      </div>
                    </td>
                    <td>
                      <Link to={`/signals/${s.signal_uuid}`} className="link-mono">Detail</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
