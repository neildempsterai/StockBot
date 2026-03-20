import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type {
  HealthResponse,
  MetricsSummaryResponse,
  StrategiesResponse,
  OpportunitiesNowResponse,
  OpportunitiesSummaryResponse,
  OpportunitiesSessionResponse,
  PaperExposureResponse,
} from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { StateBadge } from '../components/shared/StateBadge';
import { RefreshBadge } from '../components/shared/RefreshBadge';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SafetyStrip } from '../components/shared/SafetyStrip';
import { formatDateTime, formatSession } from '../utils/format';

export function CommandCenter() {
  const { data: health, isLoading: healthLoading, isFetching: healthFetching, dataUpdatedAt } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>(ENDPOINTS.health),
    refetchInterval: 15_000,
  });
  const { data: metrics, isLoading: metricsLoading, isFetching: metricsFetching } = useQuery({
    queryKey: ['metricsSummary'],
    queryFn: () => apiGet<MetricsSummaryResponse>(ENDPOINTS.metricsSummary),
    refetchInterval: 15_000,
  });
  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiGet<StrategiesResponse>(ENDPOINTS.strategies),
  });
  const { data: opportunities, isLoading: opportunitiesLoading, isError: opportunitiesError } = useQuery({
    queryKey: ['opportunitiesNow'],
    queryFn: () => apiGet<OpportunitiesNowResponse>(ENDPOINTS.opportunitiesNow),
    refetchInterval: 30_000,
  });
  const { data: opportunitiesSummary } = useQuery({
    queryKey: ['opportunitiesSummary'],
    queryFn: () => apiGet<OpportunitiesSummaryResponse>(ENDPOINTS.opportunitiesSummary),
    refetchInterval: 30_000,
  });
  const { data: sessionInfo } = useQuery({
    queryKey: ['opportunitiesSession'],
    queryFn: () => apiGet<OpportunitiesSessionResponse>(ENDPOINTS.opportunitiesSession),
    refetchInterval: 60_000,
  });
  const { data: paperExposure, isLoading: exposureLoading } = useQuery({
    queryKey: ['paperExposure'],
    queryFn: () => apiGet<PaperExposureResponse>(ENDPOINTS.paperExposure),
    refetchInterval: 15_000,
  });

  if (healthLoading || metricsLoading) {
    return (
      <div>
        <h1 className="page-title">Command Center</h1>
        <LoadingSkeleton lines={5} />
      </div>
    );
  }

  const strategy = strategies?.strategies?.[0];
  const apiOk = health?.status === 'ok';

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">Command Center</h1>
        <RefreshBadge
          dataUpdatedAt={dataUpdatedAt}
          isFetching={healthFetching || metricsFetching}
          intervalSec={15}
        />
      </div>

      <SafetyStrip />

      <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-success)' }}>
        <strong>Automation:</strong> Scanner, Scrappy, opportunity engine, and strategy worker run on their own schedules. Manual triggers in Intelligence Center and Strategy Lab are for testing and research only.
      </div>

      <section className="dashboard-section">
        <SectionHeader title="Paper Exposure Summary" subtitle="Quick status — see Portfolio for full lifecycle detail" />
        {exposureLoading && <LoadingSkeleton lines={2} />}
        {!exposureLoading && (!paperExposure?.positions || paperExposure.positions.length === 0) ? (
          <div className="grid-cards grid-cards--3">
            <KPICard title="Open Positions" value={0} />
            <KPICard title="Orphaned/Unmanaged" value={0} />
            <KPICard title="Status" value="No exposure" />
          </div>
        ) : !exposureLoading && paperExposure?.positions ? (
          <>
            {paperExposure.positions.some((p) => p.orphaned || p.managed_status === 'orphaned' || p.managed_status === 'unmanaged') && (
              <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
                <strong>⚠ Critical:</strong> {paperExposure.positions.filter(p => p.orphaned || p.managed_status === 'orphaned' || p.managed_status === 'unmanaged').length} position(s) are unmanaged or orphaned. <Link to="/portfolio" className="link-mono">Review in Portfolio →</Link>
              </div>
            )}
            {paperExposure.positions.some((p) => p.static_fallback_at_entry) && (
              <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-warning)', backgroundColor: 'var(--color-warning-bg, #2d2b1b)' }}>
                <strong>⚠ Warning:</strong> Some positions were opened using static fallback symbols. <Link to="/portfolio" className="link-mono">See details →</Link>
              </div>
            )}
            {paperExposure.positions.some((p) => !p.protection_active && p.managed_status !== 'exited') && (
              <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-warning)', backgroundColor: 'var(--color-warning-bg, #2d2b1b)' }}>
                <strong>⚠ Warning:</strong> Some positions have no active protection. <Link to="/portfolio" className="link-mono">Review exit plans →</Link>
              </div>
            )}
            <div className="grid-cards grid-cards--4">
              <KPICard title="Open Positions" value={paperExposure.positions.length} />
              <KPICard 
                title="Orphaned/Unmanaged" 
                value={paperExposure.positions.filter(p => p.orphaned || p.managed_status === 'orphaned' || p.managed_status === 'unmanaged').length}
                valueClass={paperExposure.positions.some(p => p.orphaned || p.managed_status === 'orphaned' || p.managed_status === 'unmanaged') ? 'pnl--negative' : ''}
              />
              <KPICard 
                title="Managed" 
                value={paperExposure.positions.filter(p => p.managed_status === 'managed' || p.managed_status === 'pending').length}
                valueClass={paperExposure.positions.some(p => p.managed_status === 'managed' || p.managed_status === 'pending') ? 'pnl--positive' : ''}
              />
              <KPICard 
                title="Protected" 
                value={paperExposure.positions.filter(p => p.protection_active).length}
                valueClass={paperExposure.positions.some(p => p.protection_active) ? 'pnl--positive' : ''}
              />
            </div>
            <div style={{ marginTop: '1rem', textAlign: 'center' }}>
              <Link to="/portfolio" className="link-mono" style={{ fontSize: '1rem', fontWeight: 500 }}>
                → View full lifecycle detail in Portfolio
              </Link>
            </div>
          </>
        ) : null}
      </section>

      <section className="dashboard-section">
        <SectionHeader title="System Status" subtitle="Quick health check — see System Health for details" />
        <div className="grid-cards grid-cards--3">
          <div className={`kpi-card kpi-card--status ${apiOk ? 'kpi-card--ok' : 'kpi-card--err'}`}>
            <div className="kpi-card__title">API</div>
            <div className="kpi-card__value">
              <StateBadge label={apiOk ? 'OK' : 'DOWN'} variant={apiOk ? 'success' : 'error'} />
            </div>
          </div>
          <KPICard
            title="Strategy"
            value={strategy ? strategy.strategy_id : '—'}
            subtitle={strategy ? `v${strategy.strategy_version}` : undefined}
          />
          <KPICard
            title="Session"
            value={formatSession(sessionInfo?.session)}
            subtitle={sessionInfo?.session ? 'Current session' : undefined}
          />
        </div>
        <div style={{ marginTop: '0.5rem', textAlign: 'center' }}>
          <Link to="/system-health" className="link-mono" style={{ fontSize: '0.9rem' }}>
            → Full system status
          </Link>
        </div>
      </section>


      <section className="dashboard-section">
        <SectionHeader title="Top Opportunities Now" subtitle="Scanner-ranked candidates (discovery only)" />
        {opportunitiesError && (
          <BackendNotConnected message="Scanner/opportunities endpoint unavailable" detail="Check API and scanner service." />
        )}
        {!opportunitiesError && opportunitiesLoading && <LoadingSkeleton lines={3} />}
        {!opportunitiesError && !opportunitiesLoading && (!opportunities?.opportunities?.length ? (
          <>
            <EmptyState
              message={
                opportunitiesSummary?.reason_if_blocked
                  ? `Overnight/session: ${opportunitiesSummary.reason_if_blocked}. Enable overnight scanning or wait for premarket/regular.`
                  : opportunitiesSummary?.source === 'none' && opportunitiesSummary?.reason === 'no_live_scanner_run'
                    ? 'No live scanner run yet. Bootstrap may not have run or scanner is starting.'
                    : opportunities?.run_id
                      ? 'No top candidates in this run yet.'
                      : 'No live opportunities. Check scanner logs and gateway/worker fallback reason in System Health.'
              }
              icon="🔍"
            />
            {opportunitiesSummary?.scanner_session_allowed === false && !opportunitiesSummary?.reason_if_blocked && (
              <p className="muted-text" style={{ marginTop: '0.5rem' }}>Scanning disabled for current session.</p>
            )}
          </>
        ) : (
          <>
            {opportunitiesSummary?.top_count != null && opportunitiesSummary?.top_scrappy_count != null && (
              <p className="muted-text" style={{ marginBottom: '0.5rem' }}>
                {opportunitiesSummary.top_scrappy_count} of {opportunitiesSummary.top_count} opportunities have Scrappy snapshots
              </p>
            )}
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Symbol</th>
                    <th>Score</th>
                    {(opportunities?.opportunities ?? []).some((o) => o.semantic_score != null) ? <th>Semantic</th> : null}
                    {(opportunities?.opportunities ?? []).some((o) => o.candidate_source) ? <th>Source</th> : null}
                    <th>Price</th>
                    <th>Gap %</th>
                    <th>Spread (bps)</th>
                    <th>Scrappy</th>
                    <th>Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {(opportunities?.opportunities ?? []).map((opp) => (
                    <tr key={opp.symbol}>
                      <td>{opp.rank}</td>
                      <td>
                        <Link to={`/scanner/symbol/${opp.symbol}`} className="link-mono">{opp.symbol}</Link>
                      </td>
                      <td>{opp.total_score != null ? Number(opp.total_score).toFixed(2) : '—'}</td>
                      {(opportunities?.opportunities ?? []).some((o) => o.semantic_score != null) ? (
                        <td>{opp.semantic_score != null ? Number(opp.semantic_score).toFixed(2) : '—'}</td>
                      ) : null}
                      {(opportunities?.opportunities ?? []).some((o) => o.candidate_source) ? (
                        <td>{opp.candidate_source ?? '—'}</td>
                      ) : null}
                      <td>{opp.price != null ? `$${Number(opp.price).toFixed(2)}` : '—'}</td>
                      <td>{opp.gap_pct != null ? `${Number(opp.gap_pct).toFixed(2)}%` : '—'}</td>
                      <td>{opp.spread_bps != null ? opp.spread_bps : '—'}</td>
                      <td>
                        {opp.scrappy_present ? (
                          <span style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', alignItems: 'flex-start' }}>
                            <span>✓</span>
                            {opp.scrappy_catalyst_direction && (
                              <span className="badge badge--dim">{opp.scrappy_catalyst_direction}</span>
                            )}
                            {(opp.scrappy_stale_flag || opp.scrappy_conflict_flag) && (
                              <span>
                                {opp.scrappy_stale_flag && <span className="flag-badge flag-badge--warn">stale</span>}
                                {opp.scrappy_conflict_flag && <span className="flag-badge flag-badge--warn">conflict</span>}
                              </span>
                            )}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>
                        <span className="reason-codes">
                          {((opp.inclusion_reasons ?? opp.reason_codes) ?? []).slice(0, 3).join(', ')}
                          {((opp.inclusion_reasons ?? opp.reason_codes) ?? []).length > 3 ? '…' : ''}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ))}
        {!opportunitiesError && opportunities?.updated_at && (
          <p className="muted-text" style={{ marginTop: '0.5rem' }}>
            Updated {formatDateTime(opportunities.updated_at)}
          </p>
        )}
      </section>


    </div>
  );
}
