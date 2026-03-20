import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';
import { ENDPOINTS } from '../../api/endpoints';
import type { HealthResponse, StrategiesResponse } from '../../types/api';
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
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: () => apiGet<Record<string, unknown>>(ENDPOINTS.config),
    refetchInterval: 60_000,
  });

  const strategy = strategies?.strategies?.[0];
  const strategyLabel = strategy ? `${strategy.strategy_id} / ${strategy.strategy_version}` : '—';
  const modeLabel = strategy?.mode ?? '—';
  const apiOk = health?.status === 'ok';
  const scrappyMode = (config?.SCRAPPY_MODE as string) ?? '—';
  const refereeMode = (config?.AI_REFEREE_ENABLED ? (config?.AI_REFEREE_MODE as string) : 'off') ?? '—';

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null;

  return (
    <header className="topbar">
      <div className="topbar__left">
        <div className="topbar__live-dot" title="Live — polling every 30s" />
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
        <StateBadge label={strategyLabel} variant="default" />
        <StateBadge label={modeLabel} variant="default" />
        <StateBadge label={`scrappy ${scrappyMode}`} variant="neutral" />
        <StateBadge label={`referee ${refereeMode}`} variant="neutral" />
      </div>
    </header>
  );
}
