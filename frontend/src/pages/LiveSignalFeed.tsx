import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { EmptyState } from '../components/shared/EmptyState';
import { SectionHeader } from '../components/shared/SectionHeader';
import { formatTs } from '../utils/format';

interface SignalRow {
  signal_uuid: string;
  symbol?: string;
  side?: string;
  qty?: number;
  quote_ts?: string;
  strategy_id?: string;
  strategy_version?: string;
  reason_codes?: string[];
}

export function LiveSignalFeed() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['signals'],
    queryFn: () => apiGet<{ signals?: SignalRow[] }>(`${ENDPOINTS.signals}?limit=50`),
    refetchInterval: 15_000,
  });

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Live Signals</h1>
        <LoadingSkeleton lines={8} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Live Signals</h1>
        <BackendNotConnected message="Could not load signals" />
      </div>
    );
  }

  const signals = data?.signals ?? [];

  return (
    <div className="page-stack">
      <h1 className="page-title">Live Signals</h1>
      <SectionHeader title="Recent signals" subtitle="Strategy-generated signals (deterministic authority)" />
      {signals.length === 0 ? (
        <EmptyState message="No signals yet." icon="⚡" />
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Time</th>
                <th>Strategy</th>
                <th>Reasons</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s) => (
                <tr key={s.signal_uuid}>
                  <td className="cell--symbol">{s.symbol}</td>
                  <td>
                    <span className={s.side?.toLowerCase() === 'buy' ? 'signal-side signal-side--buy' : 'signal-side signal-side--sell'}>
                      {s.side?.toUpperCase()}
                    </span>
                  </td>
                  <td>{s.qty}</td>
                  <td className="cell--ts">{formatTs(s.quote_ts)}</td>
                  <td>{s.strategy_id ?? '—'}</td>
                  <td className="cell--muted cell--small">{(s.reason_codes ?? []).slice(0, 2).join(', ')}</td>
                  <td>
                    <Link to={`/signals/${s.signal_uuid}`} className="link-mono">Detail</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
