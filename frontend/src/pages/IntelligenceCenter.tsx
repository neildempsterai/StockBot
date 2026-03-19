import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type {
  IntelligenceRecentResponse,
  IntelligenceSummaryResponse,
  ScrappyStatusResponse,
  ScrappyAutoRunsResponse,
} from '../types/api';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { KPICard } from '../components/shared/KPICard';
import { RefreshBadge } from '../components/shared/RefreshBadge';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { formatTs } from '../utils/format';

export function IntelligenceCenter() {
  const queryClient = useQueryClient();
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
  const { data: scrappyStatus } = useQuery({
    queryKey: ['scrappyStatus'],
    queryFn: () => apiGet<ScrappyStatusResponse>(ENDPOINTS.scrappyStatus),
    refetchInterval: 30_000,
  });
  const { data: autoRuns } = useQuery({
    queryKey: ['scrappyAutoRuns'],
    queryFn: () => apiGet<ScrappyAutoRunsResponse>(`${ENDPOINTS.scrappyAutoRuns}?limit=5`),
    refetchInterval: 30_000,
  });
  const runScrappyMutation = useMutation({
    mutationFn: () =>
      apiPost<{ run_id?: string; outcome_code?: string; notes_created?: number; run_type?: string }>(
        ENDPOINTS.scrappyRun,
        { run_type: 'sweep' }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['intelligenceRecent'] });
      queryClient.invalidateQueries({ queryKey: ['intelligenceSummary'] });
      queryClient.invalidateQueries({ queryKey: ['scrappyStatus'] });
      queryClient.invalidateQueries({ queryKey: ['scrappyAutoRuns'] });
    },
  });
  const runWatchlistMutation = useMutation({
    mutationFn: () =>
      apiPost<{ run_id?: string; outcome_code?: string; notes_created?: number; run_type?: string }>(
        ENDPOINTS.scrappyRunWatchlist
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['intelligenceRecent'] });
      queryClient.invalidateQueries({ queryKey: ['intelligenceSummary'] });
      queryClient.invalidateQueries({ queryKey: ['scrappyStatus'] });
      queryClient.invalidateQueries({ queryKey: ['scrappyAutoRuns'] });
    },
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
  const autoEnabled = scrappyStatus?.scrappy_auto_enabled ?? false;
  const lastRunAt = scrappyStatus?.last_run_at ?? null;
  const watchlistSize = scrappyStatus?.watchlist_size ?? 0;
  const staleCount = summary?.stale_count ?? 0;
  const conflictCount = summary?.conflict_count ?? 0;
  const freshCount = summary?.fresh_count ?? 0;

  const safeStrength = (v: unknown): string | null =>
    v == null ? null : typeof v === 'string' ? v : String(v);
  const safeBool = (v: unknown): boolean => v === true || v === 'true' || v === 1;

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">Intelligence Center</h1>
        <RefreshBadge dataUpdatedAt={dataUpdatedAt} isFetching={isFetching} intervalSec={30} />
      </div>

      <div className="info-note" style={{ marginBottom: '1.25rem', borderLeft: '3px solid var(--color-success)' }}>
        <strong>Automation:</strong> Scrappy runs automatically on a schedule (scanner top symbols). You do not need to trigger it manually. The buttons below are for testing or one-off overrides only.
      </div>
      <SectionHeader
        title="Scrappy intelligence"
        subtitle={
          autoEnabled
            ? 'Auto-run is on. Snapshots feed opportunity ranking and signal gating.'
            : 'Auto-run is disabled. Enable SCRAPPY_AUTO_ENABLED in .env or use manual run below.'
        }
      />
      <div className="grid-cards" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))' }}>
        <KPICard title="Auto-run" value={autoEnabled ? 'On' : 'Off'} />
        <KPICard title="Last auto run" value={lastRunAt ? formatTs(lastRunAt) : '—'} />
        <KPICard title="Symbols covered" value={symbolsCount} />
        <KPICard title="Snapshots total" value={total} />
        <KPICard title="Fresh" value={freshCount} />
        <KPICard title="Stale" value={staleCount} />
        <KPICard title="Conflict" value={conflictCount} />
        {watchlistSize > 0 && <KPICard title="Watchlist size" value={watchlistSize} />}
      </div>
      {autoRuns?.runs?.length ? (
        <p className="muted-text" style={{ marginTop: '0.5rem' }}>
          Recent auto-runs: {autoRuns.runs.slice(0, 3).map((r) => `${r.symbols_count ?? 0} symbols, ${r.notes_created ?? 0} notes`).join('; ')}
        </p>
      ) : null}

      <SectionHeader title="Manual override (testing only)" subtitle="Trigger Scrappy on demand — not needed for normal operation" />
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={runScrappyMutation.isPending}
          onClick={() => runScrappyMutation.mutate()}
        >
          {runScrappyMutation.isPending ? 'Running…' : 'Run Scrappy (sweep)'}
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={runWatchlistMutation.isPending}
          onClick={() => runWatchlistMutation.mutate()}
        >
          {runWatchlistMutation.isPending ? 'Running…' : 'Run Scrappy (watchlist)'}
        </button>
      </div>
      {(runScrappyMutation.isError || runWatchlistMutation.isError) && (
        <p className="cell--muted" style={{ color: 'var(--color-error)', marginBottom: '1rem' }}>
          Error: {(() => {
            const err = runScrappyMutation.error || runWatchlistMutation.error;
            if (err && typeof err === 'object' && 'detail' in err) return String((err as { detail?: string }).detail);
            if (err instanceof Error) return err.message;
            return 'Request failed';
          })()}
        </p>
      )}
      {(runScrappyMutation.isSuccess || runWatchlistMutation.isSuccess) && (() => {
        const data = runScrappyMutation.isSuccess ? runScrappyMutation.data : runWatchlistMutation.data;
        return (
          <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-success)' }}>
            <strong>Run completed.</strong>
            {data && (
              <>
                {data.run_id && <> run_id: {String(data.run_id).slice(0, 16)}…</>}
                {data.outcome_code && <> outcome: {data.outcome_code}</>}
                {(data.notes_created ?? 0) > 0 && <> notes_created: {data.notes_created}</>}
              </>
            )}
            {' '}Refreshing snapshots…
          </div>
        );
      })()}

      <SectionHeader title="Recent Snapshots" subtitle="Latest 20 intelligence snapshots" />
      {snapshots.length === 0 ? (
        <EmptyState message="No snapshots yet." icon="🧠" />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
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
              {snapshots.slice(0, 20).map((s) => {
                if (!s) return null;
                const strength = safeStrength(s.catalyst_strength);
                const stale = safeBool(s.stale_flag);
                const conflict = safeBool(s.conflict_flag);
                const badgeClass = strength ? `catalyst-badge--${String(strength).toLowerCase().replace(/\s/g, '-')}` : '';
                return (
                  <tr key={s.id}>
                    <td className="cell--symbol">{String(s.symbol ?? '')}</td>
                    <td>
                      {strength != null && strength !== '' ? (
                        <span className={`catalyst-badge ${badgeClass}`.trim()}>
                          {strength}
                        </span>
                      ) : '—'}
                    </td>
                    <td>{s.catalyst_direction ?? '—'}</td>
                    <td>{s.sentiment_label ?? '—'}</td>
                    <td>{s.evidence_count ?? '—'}</td>
                    <td>{s.source_count ?? '—'}</td>
                    <td>
                      <span className={`flag-badge flag-badge--${stale ? 'warn' : 'ok'}`}>
                        {stale ? 'stale' : 'fresh'}
                      </span>
                    </td>
                    <td>
                      <span className={`flag-badge flag-badge--${conflict ? 'warn' : 'ok'}`}>
                        {conflict ? 'conflict' : 'clear'}
                      </span>
                    </td>
                    <td className="cell--ts" title={s.snapshot_ts ?? ''}>{formatTs(s.snapshot_ts)}</td>
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
