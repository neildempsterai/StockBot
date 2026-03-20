import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';

export function Experiments() {
  const { data } = useQuery({
    queryKey: ['metricsCompareScrappyModes'],
    queryFn: () => apiGet<Record<string, unknown>>(ENDPOINTS.metricsCompareScrappyModes),
    refetchInterval: 60_000,
  });

  const segments = data as Record<string, Record<string, unknown>> | undefined;

  return (
    <div className="page-stack">
      <h1 className="page-title">Experiments</h1>
      <SectionHeader title="Scrappy mode comparison" subtitle="Shadow metrics by scrappy_mode" />
      {segments && Object.keys(segments).length > 0 ? (
        <div className="grid-cards grid-cards--3">
          {Object.entries(segments).map(([mode, seg]) => (
            <div key={mode} className="kpi-card">
              <div className="kpi-card__title">{mode}</div>
              <div className="kpi-card__value">
                signals: {String(seg.signals_total ?? '—')} · trades: {String(seg.shadow_trades_total ?? '—')}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message="No segment data yet." icon="🔬" />
      )}
    </div>
  );
}
