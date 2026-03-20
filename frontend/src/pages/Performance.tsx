import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { MetricsSummaryResponse, CompareBooksResponse, PaperExposureResponse, PaperOrdersResponse, PaperOrder } from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { SectionHeader } from '../components/shared/SectionHeader';
import { formatPnl, pnlClass } from '../utils/format';

// Calculate realized P&L from orders (same logic as Orders page)
function calculateOrderPnL(order: PaperOrder, allOrders: PaperOrder[]): { realizedPnl: number | null } {
  if (order.side?.toLowerCase() !== 'sell' || order.status !== 'filled' || !order.filled_qty || !order.filled_avg_price) {
    return { realizedPnl: null };
  }
  
  const filledQty = typeof order.filled_qty === 'string' ? parseFloat(order.filled_qty) : (order.filled_qty ?? 0);
  const filledPrice = typeof order.filled_avg_price === 'string' ? parseFloat(order.filled_avg_price) : (order.filled_avg_price ?? 0);
  
  if (filledQty <= 0 || filledPrice <= 0) {
    return { realizedPnl: null };
  }

  // Find matching buy orders (FIFO)
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
    // Not all sell order matched with buy orders
    return { realizedPnl: null };
  }

  const tradeValue = filledQty * filledPrice;
  const realizedPnl = tradeValue - totalCost;
  return { realizedPnl };
}

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

  const { data: paperOrders, isLoading: ordersLoading } = useQuery({
    queryKey: ['paperOrders'],
    queryFn: () => apiGet<PaperOrdersResponse>(`${ENDPOINTS.orders}?limit=200`),
    refetchInterval: 30_000,
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

  // Shadow metrics
  const shadowPnl = metrics?.total_net_pnl_shadow ?? null;
  const signals = metrics?.signals_total ?? 0;
  const shadowTrades = metrics?.shadow_trades_total ?? 0;

  // Paper metrics
  const paperFills = compareBooks?.paper?.fill_count ?? 0;
  
  // Calculate unrealized P&L from open positions
  const paperUnrealizedPnl = paperExposure?.positions?.reduce((sum, pos) => sum + (pos.unrealized_pl ?? 0), 0) ?? 0;
  
  // Calculate realized P&L from closed trades (filled sell orders)
  const realizedPnl = paperOrders?.orders?.reduce((sum, order) => {
    const pnl = calculateOrderPnL(order, paperOrders.orders || []);
    return sum + (pnl.realizedPnl ?? 0);
  }, 0) ?? 0;
  
  // Total paper P&L = realized + unrealized
  const paperPnl = realizedPnl + paperUnrealizedPnl;

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
          value={paperPnl !== 0 ? formatPnl(paperPnl) : '—'}
          valueClass={pnlClass(paperPnl)}
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
