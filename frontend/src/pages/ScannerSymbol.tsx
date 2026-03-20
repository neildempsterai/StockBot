import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SectionHeader } from '../components/shared/SectionHeader';

export function ScannerSymbol() {
  const { symbol } = useParams<{ symbol: string }>();
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['scannerSymbol', symbol],
    queryFn: () => apiGet<Record<string, unknown>>(ENDPOINTS.scannerSymbol(symbol!)),
    enabled: !!symbol,
  });

  if (!symbol) {
    return (
      <div className="page-stack">
        <p className="muted-text">No symbol specified</p>
        <Link to="/command">← Back to Command Center</Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="page-stack">
        <SectionHeader title={`Scanner: ${symbol}`} />
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page-stack">
        <SectionHeader title={`Scanner: ${symbol}`} />
        <BackendNotConnected message="Could not load scanner data" />
        <Link to="/command">← Back to Command Center</Link>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <SectionHeader title={`Scanner: ${symbol}`} />
      
      <div className="table-wrap">
        <table className="data-table">
          <tbody>
            <tr>
              <th>Symbol</th>
              <td>{data.symbol as string}</td>
            </tr>
            <tr>
              <th>Total Score</th>
              <td>{data.total_score != null ? Number(data.total_score).toFixed(2) : '—'}</td>
            </tr>
            <tr>
              <th>Price</th>
              <td>{data.price != null ? `$${Number(data.price).toFixed(2)}` : '—'}</td>
            </tr>
            <tr>
              <th>Gap %</th>
              <td>{data.gap_pct != null ? `${Number(data.gap_pct).toFixed(2)}%` : '—'}</td>
            </tr>
            <tr>
              <th>Spread (bps)</th>
              <td>{data.spread_bps != null ? String(data.spread_bps) : '—'}</td>
            </tr>
            <tr>
              <th>Dollar Volume</th>
              <td>{data.dollar_volume_1m != null ? `$${Number(data.dollar_volume_1m).toLocaleString()}` : '—'}</td>
            </tr>
            <tr>
              <th>Relative Volume</th>
              <td>{data.rvol_5m != null ? `${Number(data.rvol_5m).toFixed(2)}x` : '—'}</td>
            </tr>
            <tr>
              <th>Status</th>
              <td>{data.candidate_status as string || '—'}</td>
            </tr>
            <tr>
              <th>Run ID</th>
              <td className="cell--mono">{data.run_id as string || '—'}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="page-stack" style={{ marginTop: '2rem' }}>
        <Link to="/command">← Back to Command Center</Link>
      </div>
    </div>
  );
}
