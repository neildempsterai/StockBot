import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet, ApiError } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { PaperOrdersResponse, PaperOrder } from '../types/api';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { formatTs } from '../utils/format';

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

function OrderRow({ order }: { order: PaperOrder }) {
  const filledPrice = order.filled_avg_price != null ? `$${parseFloat(String(order.filled_avg_price)).toFixed(2)}` : '—';
  const qty = order.qty ?? order.filled_qty ?? '—';
  const createdAt = order.created_at ? formatTs(String(order.created_at)) : '—';

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
      <td>{filledPrice}</td>
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
    <div className="page-content">
      <SectionHeader
        title="Orders"
        subtitle="Paper account orders from Alpaca"
      />

      {isLoading && <LoadingSkeleton rows={6} />}

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
            <div className="empty-state">
              <div className="empty-state__icon">📋</div>
              <div className="empty-state__msg">No {statusFilter} orders found</div>
            </div>
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
                    <th>Filled @ </th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <OrderRow key={o.id} order={o} />
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
