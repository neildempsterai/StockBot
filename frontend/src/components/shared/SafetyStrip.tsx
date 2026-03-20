import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';
import { ENDPOINTS } from '../../api/endpoints';
import type { RuntimeStatusResponse, PaperArmingPrerequisitesResponse } from '../../types/api';
import { StateBadge } from './StateBadge';

export function SafetyStrip() {
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

  const paperArmed = runtimeStatus?.paper_trading_armed ?? false;
  const paperArmedReason = runtimeStatus?.paper_armed_reason ?? 'unknown';
  const paperExecutionEnabled = runtimeStatus?.strategy?.paper_execution_enabled ?? false;
  const operatorTestEnabled = runtimeStatus?.operator_paper_test?.enabled ?? false;
  const gatewaySource = runtimeStatus?.symbol_source?.gateway?.active_source;
  const gatewayFallback = runtimeStatus?.symbol_source?.gateway?.fallback_reason;
  const workerSource = runtimeStatus?.symbol_source?.worker?.active_source;
  const workerFallback = runtimeStatus?.symbol_source?.worker?.fallback_reason;
  const dynamicUniverseStale = runtimeStatus?.symbol_source?.dynamic_universe_last_updated_at == null;
  const prerequisitesSatisfied = prerequisites?.satisfied ?? false;
  const blockers = prerequisites?.blockers ?? [];

  const isStaticFallback = gatewaySource === 'static' || workerSource === 'static';
  const hasBlockers = blockers.length > 0;

  return (
    <div
      style={{
        padding: '0.75rem 1rem',
        backgroundColor: hasBlockers || isStaticFallback || !paperArmed ? 'var(--color-error-bg, #2d1b1b)' : 'var(--color-bg-secondary, #161b22)',
        borderBottom: `2px solid ${hasBlockers || isStaticFallback ? 'var(--color-error, #f85149)' : paperArmed ? 'var(--color-success, #3fb950)' : 'var(--color-border, #30363d)'}`,
        marginBottom: '1.5rem',
      }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', fontSize: '0.9rem' }}>
        <strong style={{ marginRight: '0.5rem' }}>Safety Status:</strong>
        <StateBadge
          label={paperArmed ? 'Paper Armed' : 'Paper Disarmed'}
          variant={paperArmed ? 'success' : 'error'}
        />
        {paperArmedReason && paperArmedReason !== 'unknown' && (
          <span className="muted-text" style={{ fontSize: '0.85rem' }}>
            ({paperArmedReason.replace(/_/g, ' ')})
          </span>
        )}
        {paperExecutionEnabled && <StateBadge label="Paper Execution On" variant="default" />}
        {operatorTestEnabled && <StateBadge label="Operator Test On" variant="default" />}
        {gatewaySource && (
          <span className="muted-text" style={{ fontSize: '0.85rem' }}>
            Gateway: {gatewaySource}
            {gatewayFallback && ` (${gatewayFallback})`}
          </span>
        )}
        {workerSource && (
          <span className="muted-text" style={{ fontSize: '0.85rem' }}>
            Worker: {workerSource}
            {workerFallback && ` (${workerFallback})`}
          </span>
        )}
        {isStaticFallback && <StateBadge label="⚠ Static Fallback Active" variant="error" />}
        {dynamicUniverseStale && <StateBadge label="⚠ Dynamic Universe Stale" variant="warning" />}
        {hasBlockers && (
          <StateBadge label={`⚠ ${blockers.length} Blocker(s)`} variant="error" />
        )}
        {!prerequisitesSatisfied && !hasBlockers && (
          <StateBadge label="⚠ Prerequisites Not Met" variant="warning" />
        )}
      </div>
    </div>
  );
}
