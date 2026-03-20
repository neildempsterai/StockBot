import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { MetricsSummaryResponse, CompareBooksResponse, PaperExposureResponse, PaperOrdersResponse, PaperOrder, StrategiesResponse } from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { formatPnl, pnlClass } from '../utils/format';

function calculateOrderPnL(order: PaperOrder, allOrders: PaperOrder[]): { realizedPnl: number | null } {
  if (order.side?.toLowerCase() !== 'sell' || order.status !== 'filled' || !order.filled_qty || !order.filled_avg_price) {
    return { realizedPnl: null };
  }

  const filledQty = typeof order.filled_qty === 'string' ? parseFloat(order.filled_qty) : (order.filled_qty ?? 0);
  const filledPrice = typeof order.filled_avg_price === 'string' ? parseFloat(order.filled_avg_price) : (order.filled_avg_price ?? 0);

  if (filledQty <= 0 || filledPrice <= 0) {
    return { realizedPnl: null };
  }

  let remainingQty = filledQty;
  let totalCost = 0;
  const buyOrders = allOrders
    .filter(o => o.symbol === order.symbol && o.side?.toLowerCase() === 'buy' && o.status === 'filled' && o.filled_qty && o.filled_avg_price)
    .sort((a, b) => {
      const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
      const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
      return aTime - bTime;
    });

  for (const buyOrder of buyOrders) {
    if (remainingQty <= 0) break;
    const buyQty = typeof buyOrder.filled_qty === 'string' ? parseFloat(buyOrder.filled_qty) : (buyOrder.filled_qty ?? 0);
    const buyPrice = typeof buyOrder.filled_avg_price === 'string' ? parseFloat(buyOrder.filled_avg_price) : (buyOrder.filled_avg_price ?? 0);
    const matchedQty = Math.min(remainingQty, buyQty);
    totalCost += matchedQty * buyPrice;
    remainingQty -= matchedQty;
  }

  if (remainingQty > 0) {
    return { realizedPnl: null };
  }

  return { realizedPnl: (filledQty * filledPrice) - totalCost };
}

export function Performance() {
  const [strategyFilter, setStrategyFilter] = useState<string>('all');

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

  const { data: paperOrders, isLoading: ordersLoading } = useQuery({
    queryKey: ['paperOrders'],
    queryFn: () => apiGet<PaperOrdersResponse>(`${ENDPOINTS.orders}?limit=200`),
    refetchInterval: 30_000,
  });

  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiGet<StrategiesResponse>(ENDPOINTS.strategies),
  });

  const { data: strategyComparison } = useQuery({
    queryKey: ['metricsCompareStrategies'],
    queryFn: () => apiGet<Record<string, Record<string, unknown>>>(ENDPOINTS.metricsCompareStrategies),
    refetchInterval: 60_000,
  });

  const isLoading = metricsLoading || booksLoading || exposureLoading || ordersLoading;

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Performance</h1>
        <LoadingSkeleton lines={8} />
      </div>
    );
  }

  const allStrategies = strategies?.strategies ?? [];
  const strategyIds = allStrategies.map(s => s.strategy_id);

  const shadowPnl = metrics?.total_net_pnl_shadow ?? null;
  const signals = metrics?.signals_total ?? 0;
  const shadowTrades = metrics?.shadow_trades_total ?? 0;

  const paperFills = compareBooks?.paper?.fill_count ?? 0;
  const paperUnrealizedPnl = paperExposure?.positions?.reduce((sum, pos) => sum + (pos.unrealized_pl ?? 0), 0) ?? 0;

  const realizedPnl = paperOrders?.orders?.reduce((sum, order) => {
    const pnl = calculateOrderPnL(order, paperOrders.orders || []);
    return sum + (pnl.realizedPnl ?? 0);
  }, 0) ?? 0;

  const paperPnl = realizedPnl + paperUnrealizedPnl;

  return (
    <div className="page-stack">
      <h1 className="page-title">Performance</h1>

      {/* Shadow Book Section */}
      <SectionHeader title="Shadow Book" subtitle="Strategy performance (shadow fills only)" />
      <div className="grid-cards grid-cards--4">
        <KPICard title="Signals" value={signals} />
        <KPICard title="Shadow Trades" value={shadowTrades} variant="shadow" />
        <KPICard
          title="Net P&L (Shadow)"
          value={shadowPnl != null ? formatPnl(shadowPnl) : '—'}
          variant="shadow"
          valueClass={pnlClass(shadowPnl)}
        />
        <KPICard
          title="Win Rate"
          value={
            shadowTrades > 0
              ? `${(Number(metrics?.['shadow_trades_winners'] ?? 0) / shadowTrades * 100).toFixed(0)}%`
              : '—'
          }
          subtitle={shadowTrades > 0 ? `${metrics?.['shadow_trades_winners'] ?? 0}W / ${metrics?.['shadow_trades_losers'] ?? 0}L` : undefined}
        />
      </div>

      {/* Paper Trading Section */}
      <SectionHeader title="Paper Trading" subtitle="Real broker fills and live P&L" />
      <div className="grid-cards grid-cards--4">
        <KPICard title="Paper Fills" value={paperFills} />
        <KPICard
          title="Paper P&L"
          value={paperPnl !== 0 ? formatPnl(paperPnl) : '—'}
          valueClass={pnlClass(paperPnl)}
        />
        <KPICard
          title="Open Positions"
          value={paperExposure?.positions?.length ?? 0}
        />
        <KPICard
          title="Unrealized P&L"
          value={paperUnrealizedPnl !== 0 ? formatPnl(paperUnrealizedPnl) : '—'}
          valueClass={pnlClass(paperUnrealizedPnl)}
        />
      </div>

      {/* Per-Strategy Breakdown */}
      {strategyComparison && Object.keys(strategyComparison).length > 0 && (
        <>
          <SectionHeader title="Per-Strategy Breakdown" subtitle="Shadow metrics segmented by strategy" />
          <div className="filter-row">
            <button
              className={`filter-btn${strategyFilter === 'all' ? ' filter-btn--active' : ''}`}
              onClick={() => setStrategyFilter('all')}
            >
              All
            </button>
            {strategyIds.map(id => (
              <button
                key={id}
                className={`filter-btn${strategyFilter === id ? ' filter-btn--active' : ''}`}
                onClick={() => setStrategyFilter(id)}
              >
                {id}
              </button>
            ))}
          </div>

          {strategyFilter === 'all' ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>Signals</th>
                    <th>Shadow Trades</th>
                    <th>Net P&L</th>
                    <th>Avg Trade</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(strategyComparison).map(([stratId, seg]) => (
                    <tr key={stratId}>
                      <td className="cell--symbol">{stratId}</td>
                      <td>{String(seg.signals_total ?? 0)}</td>
                      <td>{String(seg.shadow_trades_total ?? 0)}</td>
                      <td className={pnlClass(seg.total_net_pnl_shadow as number | null)}>
                        {seg.total_net_pnl_shadow != null ? formatPnl(seg.total_net_pnl_shadow as number) : '—'}
                      </td>
                      <td className={pnlClass(seg.avg_net_pnl_shadow as number | null)}>
                        {seg.avg_net_pnl_shadow != null ? formatPnl(seg.avg_net_pnl_shadow as number) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            (() => {
              const seg = strategyComparison[strategyFilter] ?? {};
              return (
                <div className="grid-cards grid-cards--4">
                  <KPICard title="Signals" value={String(seg.signals_total ?? 0)} />
                  <KPICard title="Shadow Trades" value={String(seg.shadow_trades_total ?? 0)} variant="shadow" />
                  <KPICard
                    title="Net P&L"
                    value={seg.total_net_pnl_shadow != null ? formatPnl(seg.total_net_pnl_shadow as number) : '—'}
                    variant="shadow"
                    valueClass={pnlClass(seg.total_net_pnl_shadow as number | null)}
                  />
                  <KPICard
                    title="Avg Trade"
                    value={seg.avg_net_pnl_shadow != null ? formatPnl(seg.avg_net_pnl_shadow as number) : '—'}
                    valueClass={pnlClass(seg.avg_net_pnl_shadow as number | null)}
                  />
                </div>
              );
            })()
          )}
        </>
      )}

      {(!strategyComparison || Object.keys(strategyComparison).length === 0) && allStrategies.length > 0 && (
        <>
          <SectionHeader title="Per-Strategy Breakdown" subtitle="Shadow metrics segmented by strategy" />
          <EmptyState message="No per-strategy comparison data yet. Trades must be recorded first." icon="📊" />
        </>
      )}
    </div>
  );
}
