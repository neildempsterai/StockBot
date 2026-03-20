import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { StateBadge } from '../components/shared/StateBadge';
import { formatTs } from '../utils/format';
import type { PaperExposureResponse } from '../types/api';

interface Assessment {
  assessment_id: string;
  symbol?: string;
  decision_class?: string;
  setup_quality_score?: number;
  plain_english_rationale?: string;
  assessment_ts?: string;
  [key: string]: unknown;
}

export function AiReferee() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['aiRefereeRecent'],
    queryFn: () => apiGet<{ assessments?: Assessment[] }>(`${ENDPOINTS.aiRefereeRecent}?limit=20`),
    refetchInterval: 30_000,
  });
  const { data: paperExposure } = useQuery({
    queryKey: ['paperExposure'],
    queryFn: () => apiGet<PaperExposureResponse>(ENDPOINTS.paperExposure),
    refetchInterval: 15_000,
  });
  
  // Create a map of symbols with open positions
  const symbolsWithOpenPositions = new Set(
    paperExposure?.positions?.map(p => p.symbol?.toUpperCase()).filter(Boolean) ?? []
  );

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">AI Referee</h1>
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-stack">
        <h1 className="page-title">AI Referee</h1>
        <BackendNotConnected message="Could not load AI referee assessments" />
      </div>
    );
  }

  const assessments = data?.assessments ?? (Array.isArray(data) ? (data as Assessment[]) : []);

  return (
    <div className="page-stack">
      <h1 className="page-title">AI Referee</h1>
      <SectionHeader title="Recent assessments" subtitle="Advisory only — not order authority" />
      {assessments.length === 0 ? (
        <EmptyState message="No referee assessments yet. Enable AI_REFEREE_ENABLED and ensure candidates reach the referee." icon="🤖" />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Live Position</th>
                <th>Decision</th>
                <th>Score</th>
                <th>Time</th>
                <th>Rationale</th>
              </tr>
            </thead>
            <tbody>
              {assessments.map((a) => {
                const symbolUpper = String(a.symbol ?? '').toUpperCase();
                const hasOpenPosition = symbolsWithOpenPositions.has(symbolUpper);
                const position = paperExposure?.positions?.find(p => p.symbol?.toUpperCase() === symbolUpper);
                return (
                  <tr 
                    key={a.assessment_id}
                    style={hasOpenPosition ? { backgroundColor: 'var(--color-success-bg, rgba(63, 185, 80, 0.1))' } : undefined}
                  >
                    <td className="cell--symbol">
                      {a.symbol}
                      {hasOpenPosition && position && (
                        <Link to="/portfolio" className="link-mono" style={{ fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                          View position →
                        </Link>
                      )}
                    </td>
                    <td>
                      {hasOpenPosition && position ? (
                        <div style={{ fontSize: '0.85rem' }}>
                          <StateBadge label={`${position.side?.toUpperCase()} ${position.qty}`} variant="success" />
                          <div className="muted-text" style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                            {position.unrealized_pl != null ? (
                              <span className={position.unrealized_pl >= 0 ? 'pnl--positive' : 'pnl--negative'}>
                                {position.unrealized_pl >= 0 ? '+' : ''}${position.unrealized_pl.toFixed(2)}
                              </span>
                            ) : '—'}
                          </div>
                        </div>
                      ) : (
                        <span className="muted-text">—</span>
                      )}
                    </td>
                    <td><span className="badge badge--dim">{a.decision_class ?? '—'}</span></td>
                    <td>{a.setup_quality_score ?? '—'}</td>
                    <td className="cell--ts">{formatTs(a.assessment_ts)}</td>
                    <td className="cell--muted" style={{ maxWidth: 320 }}>{(a.plain_english_rationale ?? '').slice(0, 120)}…</td>
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
