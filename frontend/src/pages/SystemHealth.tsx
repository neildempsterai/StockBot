import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { HealthDetailResponse, RuntimeStatusResponse, PaperArmingPrerequisitesResponse, ReconciliationResponse } from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { StateBadge } from '../components/shared/StateBadge';
import { formatTs } from '../utils/format';

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
    </div>
  );
}
