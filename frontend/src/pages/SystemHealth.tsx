import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { HealthDetailResponse } from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';

export function SystemHealth() {
  const { data, isLoading } = useQuery({
    queryKey: ['healthDetail'],
    queryFn: () => apiGet<HealthDetailResponse>(ENDPOINTS.healthDetail),
    refetchInterval: 15_000,
  });

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">System Health</h1>
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  return (
    <div className="page-stack">
      <h1 className="page-title">System Health</h1>
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
      {(data?.gateway_fallback_reason || data?.worker_fallback_reason) && (
        <div className="info-note" style={{ marginTop: '1rem' }}>
          Fallback: gateway — {data.gateway_fallback_reason ?? '—'} · worker — {data.worker_fallback_reason ?? '—'}
        </div>
      )}
    </div>
  );
}
