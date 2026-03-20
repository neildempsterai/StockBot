import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SectionHeader } from '../components/shared/SectionHeader';
import { KPICard } from '../components/shared/KPICard';

interface StrategyEligibilityInfo {
  eligible?: boolean;
  enabled?: boolean;
  reason?: string;
  holding_period_type?: string;
}

export function ScannerSymbol() {
  const { symbol } = useParams<{ symbol: string }>();

  const { data, isLoading, error } = useQuery({
    queryKey: ['scannerSymbol', symbol],
    queryFn: () => apiGet<Record<string, unknown>>(ENDPOINTS.scannerSymbol(symbol!)),
    enabled: !!symbol,
  });

  const { data: oppData } = useQuery({
    queryKey: ['opportunitySymbol', symbol],
    queryFn: () => apiGet<Record<string, unknown>>(ENDPOINTS.opportunitiesSymbol(symbol!)),
    enabled: !!symbol,
  });

  if (!symbol) {
    return (
      <div className="page-stack">
        <p className="muted-text">No symbol specified</p>
        <Link to="/command">Back to Command Center</Link>
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
        <Link to="/command">Back to Command Center</Link>
      </div>
    );
  }

  const strategyEligibility = (oppData?.strategy_eligibility ?? data.strategy_eligibility ?? {}) as Record<string, StrategyEligibilityInfo>;

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">{symbol}</h1>
        <Link to="/command" className="link-mono">Back to Command Center</Link>
      </div>

      <section className="dashboard-section">
        <SectionHeader title="Scanner Data" subtitle="Latest scanner snapshot" />
        <div className="grid-cards grid-cards--4">
          <KPICard title="Total Score" value={data.total_score != null ? Number(data.total_score).toFixed(2) : '—'} />
          <KPICard title="Price" value={data.price != null ? `$${Number(data.price).toFixed(2)}` : '—'} />
          <KPICard title="Gap %" value={data.gap_pct != null ? `${Number(data.gap_pct).toFixed(2)}%` : '—'} />
          <KPICard title="Spread" value={data.spread_bps != null ? `${data.spread_bps} bps` : '—'} />
        </div>
        <div className="grid-cards grid-cards--4" style={{ marginTop: '0.75rem' }}>
          <KPICard title="Dollar Volume (1m)" value={data.dollar_volume_1m != null ? `$${Number(data.dollar_volume_1m).toLocaleString()}` : '—'} />
          <KPICard title="Relative Volume (5m)" value={data.rvol_5m != null ? `${Number(data.rvol_5m).toFixed(2)}x` : '—'} />
          <KPICard title="Status" value={String(data.candidate_status ?? '—')} />
          <KPICard title="Source" value={String(data.candidate_source ?? data.source ?? '—')} />
        </div>
      </section>

      {Object.keys(strategyEligibility).length > 0 && (
        <section className="dashboard-section">
          <SectionHeader title="Strategy Eligibility" subtitle="Per-strategy trade eligibility for this symbol" />
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Type</th>
                  <th>Enabled</th>
                  <th>Eligible</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(strategyEligibility).map(([id, info]) => (
                  <tr key={id}>
                    <td className="cell--symbol">{id}</td>
                    <td>
                      <span className={info.holding_period_type === 'swing' ? 'badge badge--swing' : 'badge badge--intraday'}>
                        {info.holding_period_type === 'swing' ? 'Swing' : 'Intraday'}
                      </span>
                    </td>
                    <td>
                      <span className={info.enabled ? 'badge badge--green' : 'badge badge--dim'}>
                        {info.enabled ? 'Yes' : 'No'}
                      </span>
                    </td>
                    <td>
                      <span className={info.eligible ? 'badge badge--green' : 'badge badge--red'}>
                        {info.eligible ? 'Eligible' : 'Rejected'}
                      </span>
                    </td>
                    <td className="cell--muted">{info.reason ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="dashboard-section">
        <SectionHeader title="Raw Data" subtitle="Full API response for debugging" />
        <div className="info-note">
          <pre style={{ fontSize: '0.85rem', overflow: 'auto', maxHeight: 300 }}>
            {JSON.stringify({ scanner: data, opportunity: oppData }, null, 2)}
          </pre>
        </div>
      </section>
    </div>
  );
}
