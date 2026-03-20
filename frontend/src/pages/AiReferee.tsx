import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { formatTs } from '../utils/format';

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
                <th>Decision</th>
                <th>Score</th>
                <th>Time</th>
                <th>Rationale</th>
              </tr>
            </thead>
            <tbody>
              {assessments.map((a) => (
                <tr key={a.assessment_id}>
                  <td className="cell--symbol">{a.symbol}</td>
                  <td><span className="badge badge--dim">{a.decision_class ?? '—'}</span></td>
                  <td>{a.setup_quality_score ?? '—'}</td>
                  <td className="cell--ts">{formatTs(a.assessment_ts)}</td>
                  <td className="cell--muted" style={{ maxWidth: 320 }}>{(a.plain_english_rationale ?? '').slice(0, 120)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
