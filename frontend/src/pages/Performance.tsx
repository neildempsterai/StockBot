import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { MetricsSummaryResponse, CompareBooksResponse, PaperExposureResponse } from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { SectionHeader } from '../components/shared/SectionHeader';
import { formatPnl, pnlClass } from '../utils/format';

export function Performance() {
  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['metricsSummary'],
    queryFn: () => apiGet<MetricsSummaryResponse>(ENDPOINTS.metricsSummary),
    refetchInterval: 30_000,
  });

  const { data: compareBooks, isLoading: booksLoading } = useQuery({
    queryKey: ['compareBooks'],
    queryFn: () => apiGet<CompareBooksResponse>(ENDPOINTS.compareBooks),
    refetchInterval: 30_000,
  });

  const { data: paperExposure, isLoading: exposureLoading } = useQuery({
    queryKey: ['paperExposure'],
    queryFn: () => apiGet<PaperExposureResponse>(ENDPOINTS.paperExposure),
    refetchInterval: 15_000,
  });

  const isLoading = metricsLoading || booksLoading || exposureLoading;

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Performance</h1>
        <LoadingSkeleton lines={8} />
      </div>
    );
  }

  // Shadow metrics
  const shadowPnl = metrics?.total_net_pnl_shadow ?? null;
  const signals = metrics?.signals_total ?? 0;
  const shadowTrades = metrics?.shadow_trades_total ?? 0;

  // Paper metrics
  const paperFills = compareBooks?.paper?.fill_count ?? 0;
  // Calculate paper P&L from open positions (unrealized) + compare-books if available
  const paperUnrealizedPnl = paperExposure?.positions?.reduce((sum, pos) => sum + (pos.unrealized_pl ?? 0), 0) ?? 0;
  const paperPnl = compareBooks?.paper?.total_net_pnl ?? paperUnrealizedPnl;

  return (
    <div className="page-stack">
      <h1 className="page-title">Performance</h1>
      
      {/* Shadow Book Section */}
      <SectionHeader title="Shadow book" subtitle="Strategy performance (shadow fills only)" />
      <div className="grid-cards grid-cards--4">
        <KPICard title="Signals" value={signals} />
        <KPICard title="Shadow trades" value={shadowTrades} variant="shadow" />
        <KPICard
          title="Net P&L (shadow)"
          value={shadowPnl != null ? formatPnl(shadowPnl) : '—'}
          variant="shadow"
          valueClass={pnlClass(shadowPnl)}
        />
      </div>

      {/* Paper Trading Section */}
      <SectionHeader title="Paper trading" subtitle="Real broker fills and live P&L" />
      <div className="grid-cards grid-cards--4">
        <KPICard title="Paper fills" value={paperFills} />
        <KPICard
          title="Paper P&L"
          value={paperPnl != null ? formatPnl(paperPnl) : (paperUnrealizedPnl !== 0 ? formatPnl(paperUnrealizedPnl) : '—')}
          valueClass={pnlClass(paperPnl ?? paperUnrealizedPnl)}
        />
        <KPICard
          title="Open positions"
          value={paperExposure?.positions?.length ?? 0}
        />
        <KPICard
          title="Unrealized P&L"
          value={paperUnrealizedPnl !== 0 ? formatPnl(paperUnrealizedPnl) : '—'}
          valueClass={pnlClass(paperUnrealizedPnl)}
        />
      </div>
    </div>
  );
}
