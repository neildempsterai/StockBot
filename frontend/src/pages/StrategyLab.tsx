import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { BacktestStatusResponse, ScannerRunHistoricalResponse } from '../types/api';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';

export function StrategyLab() {
  const queryClient = useQueryClient();
  const [historicalRunIds, setHistoricalRunIds] = useState<string[] | null>(null);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['backtestStatus'],
    queryFn: () => apiGet<BacktestStatusResponse>(ENDPOINTS.backtestStatus),
    retry: 1,
  });
  const historicalMutation = useMutation({
    mutationFn: (days: number) =>
      apiPost<ScannerRunHistoricalResponse>(ENDPOINTS.scannerRunHistorical, { days }),
    onSuccess: (result) => {
      setHistoricalRunIds(result?.run_ids ?? []);
      queryClient.invalidateQueries({ queryKey: ['scannerRuns'] });
      queryClient.invalidateQueries({ queryKey: ['scannerSummary'] });
    },
  });

  const backtestAvailable = data?.available ?? false;
  const sessions = data?.sessions ?? [];
  const backtestMessage = data?.message ?? '';
  const errorDetail = error && typeof error === 'object' && 'detail' in error ? String((error as { detail?: string }).detail) : undefined;

  return (
    <div className="page-stack">
      <h1 className="page-title">Strategy Lab</h1>
      <SectionHeader
        title="Backtest Runner"
        subtitle={data ? (backtestAvailable ? `${sessions.length} replay session(s) available` : 'Historical test execution') : 'Historical test execution'}
      />
      {isLoading && <LoadingSkeleton lines={4} />}
      {isError && (
        <div className="info-note" style={{ marginBottom: '1rem', borderColor: 'var(--color-warning)' }}>
          Backtest status unavailable: {errorDetail ?? 'Could not reach API.'} Replay sessions and Run Historical Scanner below may still work if the API is up.
        </div>
      )}
      {!isLoading && data && (
        <>
          <div className="info-note" style={{ marginBottom: '1rem' }}>
            {backtestMessage}
          </div>
          {sessions.length > 0 ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Session</th>
                    <th>Date (UTC)</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.id}>
                      <td className="cell--mono">{s.id}</td>
                      <td>{s.date_utc}</td>
                      <td className="cell--muted">{s.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="cell--muted" style={{ fontSize: '0.9rem' }}>
              Run deterministic replay on the host: <code>make replay</code> or <code>python scripts/run_replay.py --session replay/session_001</code>
            </p>
          )}
        </>
      )}

      <div style={{ marginTop: '2rem' }}>
        <div className="info-note" style={{ marginBottom: '0.75rem', borderLeft: '3px solid var(--color-success)' }}>
          <strong>Automation:</strong> The live scanner runs automatically (scanner service on a schedule). The buttons below are optional research backfills only — run when you want historical candidate data for analysis.
        </div>
        <SectionHeader
          title="Run Historical Scanner"
          subtitle="Optional backfill over past days (research). Live scanner is already automated."
        />
      </div>
      <div className="info-note" style={{ marginBottom: '1rem' }}>
        POST /v1/scanner/run/historical. Returns run IDs; view runs in Command Center.
      </div>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          type="button"
          className="btn btn--primary"
          disabled={historicalMutation.isPending}
          onClick={() => historicalMutation.mutate(30)}
        >
          {historicalMutation.isPending ? 'Running… (can take 1–5 min)' : 'Run 30-day historical'}
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={historicalMutation.isPending}
          onClick={() => historicalMutation.mutate(90)}
        >
          {historicalMutation.isPending ? 'Running… (can take 1–5 min)' : 'Run 90-day historical'}
        </button>
      </div>
      {historicalMutation.isSuccess && historicalMutation.data && (
        <div className="info-note" style={{ marginTop: '0.75rem', borderLeft: '3px solid var(--color-success)' }}>
          <strong>Request completed.</strong> {(historicalMutation.data.run_ids?.length ?? 0) > 0
            ? `${historicalMutation.data.run_ids!.length} run(s) created. View in Command Center → Scanner runs.`
            : 'No run IDs returned (may still be processing or no trading days in range).'}
        </div>
      )}
      {historicalMutation.isError && (
        <p className="cell--muted" style={{ color: 'var(--color-error)', marginTop: '0.5rem', maxWidth: '60rem' }}>
          Error: {(() => {
            const err = historicalMutation.error as { status?: number; detail?: string };
            const raw = err?.detail ?? 'Request failed';
            const status = err?.status;
            if (status === 504 || (typeof raw === 'string' && raw.includes('504') && raw.includes('Gateway Time-out'))) {
              return 'Request timed out (504). The historical scanner can take several minutes. Try fewer days or run it again.';
            }
            if (typeof raw !== 'string') return `Request failed (status ${status ?? 'unknown'}).`;
            const firstLine = raw.split(/\n/)[0].trim();
            const short = firstLine.length > 400 ? firstLine.slice(0, 400) + '…' : firstLine;
            const statusSuffix = status ? ` (${status})` : '';
            return short.replace(/<[^>]+>/g, '').trim() || `Request failed${statusSuffix}.`;
          })()}
        </p>
      )}
      {historicalRunIds && historicalRunIds.length === 0 && !historicalMutation.isPending && (
        <p className="cell--muted" style={{ marginTop: '0.5rem' }}>Backend returned no run IDs (still processing or none).</p>
      )}
      {historicalRunIds && historicalRunIds.length > 0 && (
        <div className="table-wrap" style={{ marginTop: '1rem' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
              </tr>
            </thead>
            <tbody>
              {historicalRunIds.map((id) => (
                <tr key={id}>
                  <td className="cell--mono">{id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
