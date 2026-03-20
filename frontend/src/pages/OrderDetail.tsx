import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SectionHeader } from '../components/shared/SectionHeader';

export function OrderDetail() {
  const { orderId } = useParams<{ orderId: string }>();
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['order', orderId],
    queryFn: () => apiGet<Record<string, unknown>>(ENDPOINTS.orderDetail(orderId!)),
    enabled: !!orderId,
  });

  if (!orderId) {
    return (
      <div className="page-stack">
        <p className="muted-text">No order ID specified</p>
        <Link to="/orders">← Back to Orders</Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="page-stack">
        <SectionHeader title={`Order: ${orderId.slice(0, 16)}…`} />
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page-stack">
        <SectionHeader title={`Order: ${orderId.slice(0, 16)}…`} />
        <BackendNotConnected message="Could not load order" />
        <Link to="/orders">← Back to Orders</Link>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <SectionHeader title={`Order: ${orderId}`} />
      
      <div className="table-wrap">
        <table className="data-table">
          <tbody>
            <tr>
              <th>Order ID</th>
              <td className="cell--mono">{data.id as string || '—'}</td>
            </tr>
            <tr>
              <th>Symbol</th>
              <td>{data.symbol as string || '—'}</td>
            </tr>
            <tr>
              <th>Side</th>
              <td>{data.side as string || '—'}</td>
            </tr>
            <tr>
              <th>Type</th>
              <td>{data.order_type as string || '—'}</td>
            </tr>
            <tr>
              <th>Quantity</th>
              <td>{data.qty != null ? String(data.qty) : '—'}</td>
            </tr>
            <tr>
              <th>Filled Quantity</th>
              <td>{data.filled_qty != null ? String(data.filled_qty) : '—'}</td>
            </tr>
            <tr>
              <th>Status</th>
              <td>{data.status as string || '—'}</td>
            </tr>
            <tr>
              <th>Time in Force</th>
              <td>{data.time_in_force as string || '—'}</td>
            </tr>
            {data.limit_price != null && (
              <tr>
                <th>Limit Price</th>
                <td>${Number(data.limit_price).toFixed(2)}</td>
              </tr>
            )}
            {data.stop_price != null && (
              <tr>
                <th>Stop Price</th>
                <td>${Number(data.stop_price).toFixed(2)}</td>
              </tr>
            )}
            {data.filled_avg_price != null && (
              <tr>
                <th>Filled Avg Price</th>
                <td>${Number(data.filled_avg_price).toFixed(2)}</td>
              </tr>
            )}
            <tr>
              <th>Created At</th>
              <td>{data.created_at as string || '—'}</td>
            </tr>
            <tr>
              <th>Updated At</th>
              <td>{data.updated_at as string || '—'}</td>
            </tr>
            {data.submitted_at ? (
              <tr>
                <th>Submitted At</th>
                <td>{String(data.submitted_at)}</td>
              </tr>
            ) : null}
            {data.filled_at ? (
              <tr>
                <th>Filled At</th>
                <td>{String(data.filled_at)}</td>
              </tr>
            ) : null}
            {data.canceled_at ? (
              <tr>
                <th>Canceled At</th>
                <td>{String(data.canceled_at)}</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <Link to="/orders">← Back to Orders</Link>
      </div>
    </div>
  );
}
