import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiGet, apiPost } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { 
  HealthDetailResponse, 
  RuntimeStatusResponse, 
  PaperArmingPrerequisitesResponse, 
  ReconciliationResponse, 
  PaperExposureResponse,
  ConfigResponse,
  PaperTestProofResponse,
  ScannerSummaryResponse,
  ScannerRunsResponse,
} from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { StateBadge } from '../components/shared/StateBadge';
import { formatTs, formatDateTime } from '../utils/format';

function PaperTradingControls({ 
  paperArmed, 
  prerequisitesSatisfied, 
  blockers 
}: { 
  paperArmed: boolean; 
  prerequisitesSatisfied: boolean; 
  blockers: string[];
}) {
  const queryClient = useQueryClient();
  
  const armMutation = useMutation({
    mutationFn: () => apiPost<{ armed: boolean; message: string }>(ENDPOINTS.paperArm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runtimeStatus'] });
      queryClient.invalidateQueries({ queryKey: ['paperArmingPrerequisites'] });
    },
  });
  
  const disarmMutation = useMutation({
    mutationFn: () => apiPost<{ armed: boolean; message: string }>(ENDPOINTS.paperDisarm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runtimeStatus'] });
      queryClient.invalidateQueries({ queryKey: ['paperArmingPrerequisites'] });
    },
  });
  
  const refreshPrerequisitesMutation = useMutation({
    mutationFn: () => apiGet<PaperArmingPrerequisitesResponse>(ENDPOINTS.paperArmingPrerequisites),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paperArmingPrerequisites'] });
    },
  });
  
  return (
    <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: 'var(--color-bg-secondary, #1a1a1a)', borderRadius: '4px', border: '1px solid var(--color-border)' }}>
      <h3 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '1rem' }}>Paper Trading Controls</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
        <button
          onClick={() => refreshPrerequisitesMutation.mutate()}
          disabled={refreshPrerequisitesMutation.isPending}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '0.9rem',
            backgroundColor: 'var(--color-bg-tertiary, #21262d)',
            color: 'var(--color-text, #c9d1d9)',
            border: '1px solid var(--color-border, #30363d)',
            borderRadius: '4px',
            cursor: refreshPrerequisitesMutation.isPending ? 'not-allowed' : 'pointer',
            opacity: refreshPrerequisitesMutation.isPending ? 0.6 : 1,
          }}
        >
          {refreshPrerequisitesMutation.isPending ? 'Checking...' : 'Refresh Prerequisites'}
        </button>
        <button
          onClick={() => {
            if (window.confirm('Arm paper trading? This will allow the strategy to submit paper orders to Alpaca.')) {
              armMutation.mutate();
            }
          }}
          disabled={armMutation.isPending || paperArmed || !prerequisitesSatisfied || blockers.length > 0}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '0.9rem',
            backgroundColor: prerequisitesSatisfied && blockers.length === 0 ? 'var(--color-success, #3fb950)' : 'var(--color-bg-tertiary, #21262d)',
            color: prerequisitesSatisfied && blockers.length === 0 ? '#fff' : 'var(--color-text-muted, #8b949e)',
            border: '1px solid var(--color-border, #30363d)',
            borderRadius: '4px',
            cursor: (armMutation.isPending || paperArmed || !prerequisitesSatisfied || blockers.length > 0) ? 'not-allowed' : 'pointer',
            opacity: (armMutation.isPending || paperArmed || !prerequisitesSatisfied || blockers.length > 0) ? 0.6 : 1,
          }}
        >
          {armMutation.isPending ? 'Arming...' : 'Arm Paper Trading'}
        </button>
        <button
          onClick={() => {
            if (window.confirm('Disarm paper trading? This will immediately stop all paper order submissions.')) {
              disarmMutation.mutate();
            }
          }}
          disabled={disarmMutation.isPending || !paperArmed}
          style={{
            padding: '0.5rem 1rem',
            fontSize: '0.9rem',
            backgroundColor: paperArmed ? 'var(--color-error, #f85149)' : 'var(--color-bg-tertiary, #21262d)',
            color: paperArmed ? '#fff' : 'var(--color-text-muted, #8b949e)',
            border: '1px solid var(--color-border, #30363d)',
            borderRadius: '4px',
            cursor: (disarmMutation.isPending || !paperArmed) ? 'not-allowed' : 'pointer',
            opacity: (disarmMutation.isPending || !paperArmed) ? 0.6 : 1,
          }}
        >
          {disarmMutation.isPending ? 'Disarming...' : 'Disarm Paper Trading'}
        </button>
      </div>
      {armMutation.isError && (
        <div className="info-note" style={{ marginTop: '0.75rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
          <strong>Error arming:</strong> {armMutation.error && typeof armMutation.error === 'object' && 'detail' in armMutation.error ? String(armMutation.error.detail) : 'Unknown error'}
        </div>
      )}
      {disarmMutation.isError && (
        <div className="info-note" style={{ marginTop: '0.75rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
          <strong>Error disarming:</strong> {disarmMutation.error && typeof disarmMutation.error === 'object' && 'detail' in disarmMutation.error ? String(disarmMutation.error.detail) : 'Unknown error'}
        </div>
      )}
      {armMutation.isSuccess && (
        <div className="info-note" style={{ marginTop: '0.75rem', borderLeft: '3px solid var(--color-success)', backgroundColor: 'var(--color-success-bg, #1a2e1a)' }}>
          <strong>Success:</strong> {armMutation.data?.message ?? 'Paper trading armed'}
        </div>
      )}
      {disarmMutation.isSuccess && (
        <div className="info-note" style={{ marginTop: '0.75rem', borderLeft: '3px solid var(--color-warning)', backgroundColor: 'var(--color-warning-bg, #2d2b1b)' }}>
          <strong>Success:</strong> {disarmMutation.data?.message ?? 'Paper trading disarmed'}
        </div>
      )}
      {!prerequisitesSatisfied && blockers.length > 0 && (
        <div className="muted-text" style={{ marginTop: '0.75rem', fontSize: '0.85rem' }}>
          Cannot arm: {blockers.join(', ')}
        </div>
      )}
    </div>
  );
}

export function SystemHealth() {
  const { data, isLoading } = useQuery({
    queryKey: ['healthDetail'],
    queryFn: () => apiGet<HealthDetailResponse>(ENDPOINTS.healthDetail),
    refetchInterval: 15_000,
  });
  const { data: runtimeStatus } = useQuery({
    queryKey: ['runtimeStatus'],
    queryFn: () => apiGet<RuntimeStatusResponse>(ENDPOINTS.runtimeStatus),
    refetchInterval: 15_000,
  });
  const { data: prerequisites } = useQuery({
    queryKey: ['paperArmingPrerequisites'],
    queryFn: () => apiGet<PaperArmingPrerequisitesResponse>(ENDPOINTS.paperArmingPrerequisites),
    refetchInterval: 15_000,
  });
  const { data: reconciliation } = useQuery({
    queryKey: ['reconciliation'],
    queryFn: () => apiGet<ReconciliationResponse>(ENDPOINTS.systemReconciliation),
    refetchInterval: 30_000,
  });
  const { data: paperExposure } = useQuery({
    queryKey: ['paperExposure'],
    queryFn: () => apiGet<PaperExposureResponse>(ENDPOINTS.paperExposure),
    refetchInterval: 15_000,
  });
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: () => apiGet<ConfigResponse>(ENDPOINTS.config),
    refetchInterval: 60_000,
  });
  const { data: paperTestProof } = useQuery({
    queryKey: ['paperTestProof'],
    queryFn: () => apiGet<PaperTestProofResponse>(ENDPOINTS.paperTestProof),
    refetchInterval: 30_000,
  });
  const { data: scannerSummary } = useQuery({
    queryKey: ['scannerSummary'],
    queryFn: () => apiGet<ScannerSummaryResponse>(ENDPOINTS.scannerSummary),
    refetchInterval: 30_000,
  });
  const { data: scannerRuns } = useQuery({
    queryKey: ['scannerRuns'],
    queryFn: () => apiGet<ScannerRunsResponse>(ENDPOINTS.scannerRuns),
    refetchInterval: 30_000,
  });
  
  const orphanedCount = paperExposure?.positions?.filter(p => p.orphaned || p.managed_status === 'orphaned' || p.managed_status === 'unmanaged').length ?? 0;
  const openPositionsCount = paperExposure?.positions?.length ?? 0;

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">System Health</h1>
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  const paperArmed = runtimeStatus?.paper_trading_armed ?? false;
  const paperArmedReason = runtimeStatus?.paper_armed_reason ?? 'unknown';
  const paperExecutionEnabled = runtimeStatus?.strategy?.paper_execution_enabled ?? false;
  const operatorTestEnabled = runtimeStatus?.operator_paper_test?.enabled ?? false;
  const gatewaySource = runtimeStatus?.symbol_source?.gateway?.active_source;
  const gatewayFallback = runtimeStatus?.symbol_source?.gateway?.fallback_reason;
  const workerSource = runtimeStatus?.symbol_source?.worker?.active_source;
  const workerFallback = runtimeStatus?.symbol_source?.worker?.fallback_reason;
  const prerequisitesSatisfied = prerequisites?.satisfied ?? false;
  const blockers = prerequisites?.blockers ?? [];
  const isStaticFallback = gatewaySource === 'static' || workerSource === 'static';

  return (
    <div className="page-stack">
      <h1 className="page-title">System Health</h1>

      <section className="dashboard-section">
        <SectionHeader title="Paper Trading Safety Posture" subtitle="Armed state, prerequisites, and safety checks" />
        <div className="grid-cards grid-cards--4">
          <div>
            <div className="kpi-card__title">Paper Armed</div>
            <div className="kpi-card__value">
              <StateBadge
                label={paperArmed ? 'Armed' : 'Disarmed'}
                variant={paperArmed ? 'success' : 'error'}
              />
            </div>
            <div className="muted-text" style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
              {paperArmedReason.replace(/_/g, ' ')}
            </div>
          </div>
          <KPICard
            title="Paper Execution"
            value={paperExecutionEnabled ? 'Enabled' : 'Disabled'}
          />
          <KPICard
            title="Operator Test"
            value={operatorTestEnabled ? 'Enabled' : 'Disabled'}
          />
          <div>
            <div className="kpi-card__title">Prerequisites</div>
            <div className="kpi-card__value">
              <StateBadge
                label={prerequisitesSatisfied ? 'Satisfied' : 'Not Met'}
                variant={prerequisitesSatisfied ? 'success' : 'error'}
              />
            </div>
            {blockers.length > 0 && (
              <div className="muted-text" style={{ fontSize: '0.85rem', marginTop: '0.25rem', color: 'var(--color-error)' }}>
                {blockers.length} blocker(s)
              </div>
            )}
          </div>
        </div>
        {blockers.length > 0 && (
          <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
            <strong>Blockers:</strong> {blockers.join(', ')}
          </div>
        )}
        {prerequisites?.checks && Object.keys(prerequisites.checks).length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <strong>Prerequisite Checks:</strong>
            <div style={{ marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {Object.entries(prerequisites.checks).map(([key, check]) => (
                <div key={key} style={{ fontSize: '0.85rem' }}>
                  <StateBadge
                    label={`${key}: ${check.detail ?? (check.ok ? 'ok' : 'failed')}`}
                    variant={check.ok ? 'success' : 'error'}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
        <PaperTradingControls 
          paperArmed={paperArmed}
          prerequisitesSatisfied={prerequisitesSatisfied}
          blockers={blockers}
        />
      </section>

      <section className="dashboard-section">
        <SectionHeader title="Services" subtitle="API, DB, Redis, worker, gateway" />
        <div className="grid-cards grid-cards--4">
          <KPICard title="API" value={data?.api ?? '—'} />
          <KPICard title="Database" value={data?.database ?? '—'} />
          <KPICard title="Redis" value={data?.redis ?? '—'} />
          <KPICard title="Worker" value={data?.worker ?? '—'} />
          <KPICard title="Gateway" value={data?.alpaca_gateway ?? '—'} />
          <KPICard title="Gateway symbols" value={data?.gateway_symbol_count ?? '—'} />
          <KPICard title="Worker universe" value={data?.worker_universe_count ?? '—'} />
          <KPICard title="Dynamic symbols" value={data?.dynamic_symbols_available ? 'Yes' : 'No'} />
        </div>
      </section>

      <section className="dashboard-section">
        <SectionHeader title="Symbol Source & Universe" subtitle="Dynamic vs static fallback status" />
        <div className="grid-cards grid-cards--4">
          <div>
            <div className="kpi-card__title">Gateway Source</div>
            <div className="kpi-card__value">
              <StateBadge
                label={gatewaySource ?? 'unknown'}
                variant={gatewaySource === 'dynamic' || gatewaySource === 'hybrid' ? 'success' : isStaticFallback ? 'error' : 'warning'}
              />
            </div>
            {gatewayFallback && (
              <div className="muted-text" style={{ fontSize: '0.85rem', marginTop: '0.25rem', color: 'var(--color-error)' }}>
                {gatewayFallback}
              </div>
            )}
          </div>
          <div>
            <div className="kpi-card__title">Worker Source</div>
            <div className="kpi-card__value">
              <StateBadge
                label={workerSource ?? 'unknown'}
                variant={workerSource === 'dynamic' || workerSource === 'hybrid' ? 'success' : isStaticFallback ? 'error' : 'warning'}
              />
            </div>
            {workerFallback && (
              <div className="muted-text" style={{ fontSize: '0.85rem', marginTop: '0.25rem', color: 'var(--color-error)' }}>
                {workerFallback}
              </div>
            )}
          </div>
          <KPICard
            title="Gateway Count"
            value={runtimeStatus?.symbol_source?.gateway?.symbol_count ?? data?.gateway_symbol_count ?? '—'}
          />
          <KPICard
            title="Worker Count"
            value={runtimeStatus?.symbol_source?.worker?.symbol_count ?? data?.worker_universe_count ?? '—'}
          />
        </div>
        {isStaticFallback && (
          <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
            <strong>⚠ Static Fallback Active:</strong> Paper trading is blocked when using static fallback symbols.
          </div>
        )}
        {runtimeStatus?.symbol_source?.dynamic_universe_last_updated_at && (
          <p className="muted-text" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
            Dynamic universe last updated: {formatTs(runtimeStatus.symbol_source.dynamic_universe_last_updated_at)}
          </p>
        )}
      </section>

      <section className="dashboard-section">
        <SectionHeader title="Paper Exposure Status" subtitle="Current positions and lifecycle health" />
        <div className="grid-cards grid-cards--4">
          <KPICard title="Open Positions" value={openPositionsCount} />
          <KPICard 
            title="Orphaned/Unmanaged" 
            value={orphanedCount}
            valueClass={orphanedCount > 0 ? 'pnl--negative' : ''}
          />
          <KPICard
            title="Managed"
            value={openPositionsCount - orphanedCount}
            valueClass={openPositionsCount - orphanedCount > 0 ? 'pnl--positive' : ''}
          />
          <KPICard
            title="Broker Reachable"
            value={prerequisites?.checks?.broker_reachable?.ok ? 'Yes' : 'No'}
          />
        </div>
        {orphanedCount > 0 && (
          <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
            <strong>⚠ Warning:</strong> {orphanedCount} position(s) are orphaned or unmanaged. Review in Command Center or Portfolio.
          </div>
        )}
      </section>

      {reconciliation && (
        <section className="dashboard-section">
          <SectionHeader title="Reconciliation" subtitle="Latest reconciliation run" />
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

      {(data?.gateway_fallback_reason || data?.worker_fallback_reason) && (
        <div className="info-note" style={{ marginTop: '1rem' }}>
          Fallback: gateway — {data.gateway_fallback_reason ?? '—'} · worker — {data.worker_fallback_reason ?? '—'}
        </div>
      )}

      {config && (
        <section className="dashboard-section">
          <SectionHeader title="Execution & Modes" subtitle="Deterministic strategy is sole trade authority" />
          <div className="grid-cards grid-cards--4">
            <KPICard title="Execution mode" value={config.EXECUTION_MODE ?? '—'} />
            <KPICard title="Scrappy mode" value={config.SCRAPPY_MODE ?? '—'} />
            <KPICard title="AI referee" value={config.AI_REFEREE_ENABLED ? 'Enabled' : 'Off'} />
            <KPICard title="Paper execution" value={config.PAPER_EXECUTION_ENABLED ? 'On' : 'Off'} />
          </div>
        </section>
      )}

      <section className="dashboard-section">
        <SectionHeader title="Scanner Status" subtitle="Last run and rejection reasons" />
        <div className="grid-cards grid-cards--3">
          <KPICard
            title="Last run"
            value={scannerSummary?.last_run_ts ? formatDateTime(scannerSummary.last_run_ts) : '—'}
            subtitle={scannerSummary?.last_run_status ?? undefined}
          />
          <KPICard title="Top candidates" value={scannerSummary?.top_count ?? '—'} />
          <KPICard
            title="Universe / scored"
            value={scannerRuns?.runs?.[0] ? `${scannerRuns.runs[0].universe_size} / ${scannerRuns.runs[0].candidates_scored}` : '—'}
          />
        </div>
        {scannerSummary?.rejection_reasons && Object.keys(scannerSummary.rejection_reasons).length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <strong>Top rejection reasons</strong>
            <div className="badge-row" style={{ marginTop: '0.5rem' }}>
              {Object.entries(scannerSummary.rejection_reasons)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10)
                .map(([reason, count]) => (
                  <StateBadge key={reason} label={`${reason}: ${count}`} variant="warning" />
                ))}
            </div>
          </div>
        )}
      </section>

      {scannerRuns?.runs && scannerRuns.runs.length > 0 && (
        <section className="dashboard-section">
          <SectionHeader title="Scanner History" subtitle="Recent runs" />
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Status</th>
                  <th>Universe</th>
                  <th>Scored</th>
                  <th>Top</th>
                  <th>Session</th>
                </tr>
              </thead>
              <tbody>
                {scannerRuns.runs.slice(0, 10).map((r) => (
                  <tr key={r.run_id}>
                    <td>{r.run_ts ? formatDateTime(r.run_ts) : '—'}</td>
                    <td><StateBadge label={r.status ?? '—'} variant={r.status === 'completed' ? 'success' : 'default'} /></td>
                    <td>{r.universe_size}</td>
                    <td>{r.candidates_scored}</td>
                    <td>{r.top_candidates_count}</td>
                    <td>{r.market_session ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="dashboard-section">
        <SectionHeader title="Paper Test Proof" subtitle="Last operator-test order per flow — proves all four flows ran and are persisted" />
        <div className="grid-cards grid-cards--4">
          {(paperTestProof?.intents ?? ['buy_open', 'sell_close', 'short_open', 'buy_cover']).map((intent) => {
            const entry = paperTestProof?.proof?.[intent];
            const label = intent.replace(/_/g, ' ');
            return (
              <div key={intent} className={`kpi-card ${entry ? 'kpi-card--ok' : ''}`}>
                <div className="kpi-card__title">{label}</div>
                <div className="kpi-card__value">
                  {entry ? (
                    <>
                      <StateBadge label={entry.status ?? '—'} variant={entry.status === 'filled' ? 'success' : entry.status === 'accepted' || entry.status === 'new' ? 'default' : 'warning'} />
                      <span className="muted-text" style={{ display: 'block', marginTop: '0.25rem', fontSize: '0.85rem' }}>
                        {entry.symbol} {entry.side} {entry.qty != null ? entry.qty : ''}
                      </span>
                      {entry.order_id && (
                        <span className="muted-text" style={{ display: 'block', fontSize: '0.75rem' }} title={entry.order_id}>
                          {entry.order_id.slice(0, 12)}…
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="muted-text">Not run yet</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
