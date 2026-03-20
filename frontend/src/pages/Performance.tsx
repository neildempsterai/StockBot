import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { MetricsSummaryResponse } from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { SectionHeader } from '../components/shared/SectionHeader';
import { formatPnl } from '../utils/format';

export function Performance() {
  const { data, isLoading } = useQuery({
    queryKey: ['metricsSummary'],
    queryFn: () => apiGet<MetricsSummaryResponse>(ENDPOINTS.metricsSummary),
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Performance</h1>
        <LoadingSkeleton lines={4} />
      </div>
    );
  }

  const pnl = data?.total_net_pnl_shadow ?? null;
  const signals = data?.signals_total ?? 0;
  const trades = data?.shadow_trades_total ?? 0;

  return (
    <div className="page-stack">
      <h1 className="page-title">Performance</h1>
      <SectionHeader title="Shadow book" subtitle="Strategy performance (shadow fills only)" />
      <div className="grid-cards grid-cards--4">
        <KPICard title="Signals" value={signals} />
        <KPICard title="Shadow trades" value={trades} variant="shadow" />
        <KPICard
          title="Net P&L (shadow)"
          value={pnl != null ? formatPnl(pnl) : '—'}
          variant="shadow"
          valueClass={pnl != null ? (pnl >= 0 ? 'pnl--positive' : 'pnl--negative') : ''}
        />
      </div>
    </div>
  );
}
