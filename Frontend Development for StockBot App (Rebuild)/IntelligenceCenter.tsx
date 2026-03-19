import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { IntelligenceRecentResponse, IntelligenceSummaryResponse } from '../types/api';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { KPICard } from '../components/shared/KPICard';
import { RefreshBadge } from '../components/shared/RefreshBadge';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { formatTs } from '../utils/format';

export function IntelligenceCenter() {
  const { data: recent, isLoading: recentLoading, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['intelligenceRecent'],
    queryFn: () => apiGet<IntelligenceRecentResponse>(`${ENDPOINTS.intelligenceRecent}?limit=20`),
    refetchInterval: 30_000,
  });
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['intelligenceSummary'],
    queryFn: () => apiGet<IntelligenceSummaryResponse>(ENDPOINTS.intelligenceSummary),
    refetchInterval: 30_000,
  });

  if (recentLoading || summaryLoading) {
    return (
      <div>
        <h1 className="page-title">Intelligence Center</h1>
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (!recent && !summary) {
    return (
      <div>
        <h1 className="page-title">Intelligence Center</h1>
        <BackendNotConnected message="Could not load intelligence from API" />
      </div>
    );
  }

  const snapshots = recent?.snapshots?.filter(Boolean) ?? [];
  const total = summary?.snapshots_total ?? 0;
  const symbolsCount = summary?.symbols_with_snapshot ?? 0;

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">Intelligence Center</h1>
        <RefreshBadge dataUpdatedAt={dataUpdatedAt} isFetching={isFetching} intervalSec={30} />
      </div>
      <div className="grid-cards">
        <KPICard title="Snapshots total" value={total} />
        <KPICard title="Symbols with snapshot" value={symbolsCount} />
      </div>
      <SectionHeader title="Recent Snapshots" subtitle="Latest 20 intelligence snapshots" />
      {snapshots.length === 0 ? (
        <EmptyState message="No snapshots yet." icon="🧠" />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Catalyst</th>
                <th>Direction</th>
                <th>Sentiment</th>
                <th>Evidence</th>
                <th>Sources</th>
                <th>Stale</th>
                <th>Conflict</th>
                <th>Snapshot time</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.slice(0, 20).map((s) => s && (
                <tr key={s.id}>
                  <td className="cell--symbol">{s.symbol}</td>
                  <td>
                    {s.catalyst_strength ? (
                      <span className={`catalyst-badge catalyst-badge--${s.catalyst_strength.toLowerCase()}`}>
                        {s.catalyst_strength}
                      </span>
                    ) : '—'}
                  </td>
                  <td>{s.catalyst_direction ?? '—'}</td>
                  <td>{s.sentiment_label ?? '—'}</td>
                  <td>{s.evidence_count ?? '—'}</td>
                  <td>{s.source_count ?? '—'}</td>
                  <td>
                    <span className={`flag-badge flag-badge--${s.stale_flag ? 'warn' : 'ok'}`}>
                      {s.stale_flag ? 'stale' : 'fresh'}
                    </span>
                  </td>
                  <td>
                    <span className={`flag-badge flag-badge--${s.conflict_flag ? 'warn' : 'ok'}`}>
                      {s.conflict_flag ? 'conflict' : 'clear'}
                    </span>
                  </td>
                  <td className="cell--ts" title={s.snapshot_ts ?? ''}>{formatTs(s.snapshot_ts)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
