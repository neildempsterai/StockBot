import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet, type ApiError } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { PaperOrdersResponse, PaperOrder } from '../types/api';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { EmptyState } from '../components/shared/EmptyState';
import { formatTs, formatPnl, pnlClass } from '../utils/format';
import { SourceBadge } from '../components/shared/SourceBadge';
import { Link } from 'react-router-dom';

type OrderStatus = 'open' | 'closed' | 'all';

function statusBadgeClass(status?: string): string {
  if (!status) return '';
  const s = status.toLowerCase();
  if (s === 'filled') return 'badge badge--green';
  if (s === 'canceled' || s === 'cancelled' || s === 'expired') return 'badge badge--red';
  if (s === 'new' || s === 'accepted' || s === 'pending_new') return 'badge badge--yellow';
  if (s === 'partially_filled') return 'badge badge--blue';
  return 'badge badge--dim';
}

function sideBadgeClass(side?: string): string {
  if (!side) return '';
  return side.toLowerCase() === 'buy' ? 'signal-side signal-side--buy' : 'signal-side signal-side--sell';
}

function calculateOrderPnL(order: PaperOrder, allOrders: PaperOrder[]): { realizedPnl: number | null; realizedPnlPercent: number | null; tradeValue: number | null } {
  if (order.status?.toLowerCase() !== 'filled' || !order.symbol || !order.filled_avg_price) {
    return { realizedPnl: null, realizedPnlPercent: null, tradeValue: null };
  }

  const side = order.side?.toLowerCase();
  const filledPrice = parseFloat(String(order.filled_avg_price));
  const filledQty = parseFloat(String(order.filled_qty ?? order.qty ?? 0));
  const tradeValue = filledPrice * filledQty;

  // Only SELL orders can have realized P&L (they close positions)
  // BUY orders just open positions - no realized P&L until sold
  if (side === 'sell') {
    // Find matching buy orders for this symbol (FIFO) that occurred BEFORE this sell
    const buyOrders = allOrders
      .filter(o => 
        o.symbol === order.symbol && 
        o.side?.toLowerCase() === 'buy' && 
        o.status?.toLowerCase() === 'filled' &&
        o.created_at && 
        order.created_at &&
        new Date(o.created_at) < new Date(order.created_at)
      )
      .sort((a, b) => new Date(a.created_at!).getTime() - new Date(b.created_at!).getTime());

    let remainingQty = filledQty;
    let totalCost = 0;
    let matchedQty = 0;

    // Match this sell order with buy orders using FIFO
    for (const buyOrder of buyOrders) {
      if (remainingQty <= 0) break;
      const buyPrice = parseFloat(String(buyOrder.filled_avg_price ?? 0));
      const buyQty = parseFloat(String(buyOrder.filled_qty ?? buyOrder.qty ?? 0));
      const matchQty = Math.min(remainingQty, buyQty);
      totalCost += buyPrice * matchQty;
      matchedQty += matchQty;
      remainingQty -= matchQty;
    }

    if (matchedQty > 0) {
      const avgCost = totalCost / matchedQty;
      const realizedPnl = (filledPrice - avgCost) * matchedQty;
      const realizedPnlPercent = ((filledPrice - avgCost) / avgCost) * 100;
      return { realizedPnl, realizedPnlPercent, tradeValue };
    }
  }
  
  // For BUY orders: no realized P&L (position not closed yet)
  // For SELL orders without matching buys: can't calculate (might be short cover)
  return { realizedPnl: null, realizedPnlPercent: null, tradeValue };
}

function OrderRow({ order, allOrders }: { order: PaperOrder; allOrders: PaperOrder[] }) {
  const filledPrice = order.filled_avg_price != null ? `$${parseFloat(String(order.filled_avg_price)).toFixed(2)}` : '—';
  const qty = order.qty ?? order.filled_qty ?? '—';
  const createdAt = order.created_at ? formatTs(String(order.created_at)) : '—';
  const pnl = calculateOrderPnL(order, allOrders);
  const tradeValue = pnl.tradeValue != null ? `$${pnl.tradeValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';

  return (
    <tr>
      <td className="cell--symbol">{order.symbol}</td>
      <td>
        {order.side && (
          <span className={sideBadgeClass(order.side)}>{order.side.toUpperCase()}</span>
        )}
      </td>
                      <td>{qty}</td>
                      <td>{order.order_type ?? order.type ?? '—'}</td>
                      <td>
                        {order.status && (
                          <span className={statusBadgeClass(order.status)}>{order.status}</span>
                        )}
                      </td>
                      <td>
                        <SourceBadge source={(order as any).order_source ?? (order as any).order_origin ? ((order as any).order_origin === 'strategy' ? 'strategy_paper' : (order as any).order_origin === 'operator_test' ? 'operator_test' : 'legacy_unknown') : 'legacy_unknown'} />
                        {(order as any).signal_uuid && (
                          <Link to={`/signals/${(order as any).signal_uuid}`} className="link-mono" style={{ fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                            Signal →
                          </Link>
                        )}
                      </td>
                      <td>{filledPrice}</td>
      <td>{tradeValue}</td>
      <td className={pnl.realizedPnl != null ? pnlClass(pnl.realizedPnl) : ''}>
        {pnl.realizedPnl != null ? formatPnl(pnl.realizedPnl) : '—'}
      </td>
      <td className={pnl.realizedPnlPercent != null ? pnlClass(pnl.realizedPnlPercent) : ''}>
        {pnl.realizedPnlPercent != null ? `${pnl.realizedPnlPercent >= 0 ? '+' : ''}${pnl.realizedPnlPercent.toFixed(2)}%` : '—'}
      </td>
      <td className="cell--ts">{createdAt}</td>
    </tr>
  );
}

export function Orders() {
  const [statusFilter, setStatusFilter] = useState<OrderStatus>('open');

  const { data, isLoading, error } = useQuery<PaperOrdersResponse, ApiError>({
    queryKey: ['orders', statusFilter],
    queryFn: () =>
      apiGet<PaperOrdersResponse>(ENDPOINTS.orders, { status: statusFilter, limit: 100 }),
    refetchInterval: 30_000,
  });

  const isUnconfigured = (error as ApiError)?.status === 503;
  const errorDetail = (error as ApiError)?.detail;
  const orders: PaperOrder[] = data?.orders ?? [];

  return (
    <div className="page-stack">
      <SectionHeader
        title="Orders"
        subtitle="Paper account orders from Alpaca"
      />

      {isLoading && <LoadingSkeleton lines={6} />}

      {isUnconfigured ? (
        <BackendNotConnected
          message="Alpaca not configured"
          detail={errorDetail ?? 'Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY to enable.'}
        />
      ) : error && !isUnconfigured ? (
        <BackendNotConnected message="Could not load orders" detail={errorDetail} />
      ) : !isLoading && (
        <>
          <div className="filter-row">
            {(['open', 'closed', 'all'] as OrderStatus[]).map((s) => (
              <button
                key={s}
                className={`filter-btn${statusFilter === s ? ' filter-btn--active' : ''}`}
                onClick={() => setStatusFilter(s)}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
            <span className="filter-count">{orders.length} order{orders.length !== 1 ? 's' : ''}</span>
          </div>

          {orders.length === 0 ? (
            <EmptyState message={`No ${statusFilter} orders found`} icon="📋" />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Source</th>
                    <th>Filled @</th>
                    <th>Trade Value</th>
                    <th>Realized P&L</th>
                    <th>P&L %</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <OrderRow key={o.id ?? o.symbol} order={o} allOrders={orders} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
