import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';
import { ENDPOINTS } from '../../api/endpoints';
import type { HealthResponse, StrategiesResponse, RuntimeStatusResponse } from '../../types/api';
import { StateBadge } from '../shared/StateBadge';

export function TopBar() {
  const { data: health, dataUpdatedAt } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>(ENDPOINTS.health),
    refetchInterval: 30_000,
  });
  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiGet<StrategiesResponse>(ENDPOINTS.strategies),
  });
  const { data: runtimeStatus } = useQuery({
    queryKey: ['runtimeStatus'],
    queryFn: () => apiGet<RuntimeStatusResponse>(ENDPOINTS.runtimeStatus),
    refetchInterval: 15_000,
  });

  const allStrategies = strategies?.strategies ?? [];
  const enabledStrategies = allStrategies.filter(s => s.enabled);
  const paperStrategies = allStrategies.filter(s => s.paper_enabled);
  const apiOk = health?.status === 'ok';
  const paperArmed = runtimeStatus?.paper_trading_armed ?? false;
  const executionMode = runtimeStatus?.strategy?.execution_mode ?? 'shadow';

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null;

  return (
    <header className="topbar">
      <div className="topbar__left">
        <div className="topbar__live-dot" title="Live — polling" />
        <span className="topbar__live-label">LIVE</span>
        {lastUpdated && (
          <span className="topbar__updated">updated {lastUpdated}</span>
        )}
      </div>
      <div className="topbar__badges">
        <StateBadge
          label={apiOk ? 'API ok' : 'API —'}
          variant={apiOk ? 'success' : 'neutral'}
        />
        <StateBadge
          label={paperArmed ? 'ARMED' : 'DISARMED'}
          variant={paperArmed ? 'success' : 'error'}
        />
        <StateBadge
          label={`${enabledStrategies.length} strategies`}
          variant="default"
        />
        {paperStrategies.length > 0 && (
          <StateBadge
            label={`${paperStrategies.length} paper`}
            variant="default"
          />
        )}
        <StateBadge label={executionMode} variant="neutral" />
      </div>
    </header>
  );
}
