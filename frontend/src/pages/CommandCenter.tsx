import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type {
  HealthResponse,
  StrategiesResponse,
  OpportunitiesNowResponse,
  OpportunitiesSummaryResponse,
  OpportunitiesSessionResponse,
  PaperExposureResponse,
  RuntimeStatusResponse,
  ScrappyStatusResponse,
  ScannerSummaryResponse,
  IntelligenceSummaryResponse,
} from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { StateBadge } from '../components/shared/StateBadge';
import { RefreshBadge } from '../components/shared/RefreshBadge';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SafetyStrip } from '../components/shared/SafetyStrip';
import { ManagedStatusBadge } from '../components/shared/ManagedStatusBadge';
import { formatDateTime, formatSession, formatPnl, pnlClass } from '../utils/format';

function formatMoney(s: string | number | undefined): string {
  if (s == null || s === '') return '\u2014';
  const n = typeof s === 'number' ? s : parseFloat(s as string);
  if (Number.isNaN(n)) return String(s);
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(n);
}

export function CommandCenter() {
  const { data: health, isLoading: healthLoading, isFetching: healthFetching, dataUpdatedAt } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>(ENDPOINTS.health),
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
  const { data: runtimeStatus } = useQuery({
    queryKey: ['runtimeStatus'],
    queryFn: () => apiGet<RuntimeStatusResponse>(ENDPOINTS.runtimeStatus),
    refetchInterval: 30_000,
  });
  const { data: scrappyStatus } = useQuery({
    queryKey: ['scrappyStatus'],
    queryFn: () => apiGet<ScrappyStatusResponse>(ENDPOINTS.scrappyStatus),
    refetchInterval: 30_000,
  });
  const { data: scannerSummary } = useQuery({
    queryKey: ['scannerSummary'],
    queryFn: () => apiGet<ScannerSummaryResponse>(ENDPOINTS.scannerSummary),
    refetchInterval: 30_000,
  });
  const { data: intelligenceSummary } = useQuery({
    queryKey: ['intelligenceSummary'],
    queryFn: () => apiGet<IntelligenceSummaryResponse>(ENDPOINTS.intelligenceSummary),
    refetchInterval: 30_000,
  });
  const { data: rejectionSummary } = useQuery({
    queryKey: ['signalsRejectionSummary'],
    queryFn: () => apiGet<{
      recent_rejections?: Record<string, number>;
      session?: string;
      entry_window?: string;
      in_entry_window?: boolean;
      top_rejection_reasons?: Array<[string, number]>;
      source?: string;
    }>(ENDPOINTS.signalsRejectionSummary),
    refetchInterval: 30_000,
  });

  if (healthLoading) {
    return (
      <div>
        <h1 className="page-title">Command Center</h1>
        <LoadingSkeleton lines={5} />
      </div>
    );
  }

  const allStrategies = strategies?.strategies ?? [];
  const enabledStrategies = allStrategies.filter(s => s.enabled);
  const swingStrategies = allStrategies.filter(s => s.holding_period_type === 'swing' && s.enabled);
  const apiOk = health?.status === 'ok';

  const positions = paperExposure?.positions ?? [];
  const totalUnrealizedPl = positions.reduce((s, p) => s + (p.unrealized_pl ?? 0), 0);
  const orphanedCount = positions.filter(p => p.orphaned || p.managed_status === 'orphaned' || p.managed_status === 'unmanaged').length;

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">Command Center</h1>
        <RefreshBadge
          dataUpdatedAt={dataUpdatedAt}
          isFetching={healthFetching}
          intervalSec={15}
        />
      </div>

      <SafetyStrip />

      {/* Active Strategies */}
      {allStrategies.length > 0 && (
        <section className="dashboard-section">
          <SectionHeader title="Active Strategies" subtitle="Enabled strategy lanes and rollout status" />
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Version</th>
                  <th>Type</th>
                  <th>Entry Window (ET)</th>
                  <th>Force Flat</th>
                  <th>Shadow</th>
                  <th>Paper</th>
                </tr>
              </thead>
              <tbody>
                {allStrategies.map((s) => (
                  <tr key={s.strategy_id}>
                    <td className="cell--symbol">{s.strategy_id}</td>
                    <td>{s.strategy_version ?? '—'}</td>
                    <td>
                      <span className={s.holding_period_type === 'swing' ? 'badge badge--swing' : 'badge badge--intraday'}>
                        {s.holding_period_type === 'swing' ? `Swing (${s.max_hold_days ?? 5}d max)` : 'Intraday'}
                      </span>
                    </td>
                    <td>{s.entry_window_et ?? '—'}</td>
                    <td>{s.force_flat_et ?? 'None'}</td>
                    <td><span className={s.enabled ? 'badge badge--green' : 'badge badge--dim'}>{s.enabled ? 'Yes' : 'No'}</span></td>
                    <td><span className={s.paper_enabled ? 'badge badge--green' : 'badge badge--dim'}>{s.paper_enabled ? 'Yes' : 'No'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Live Paper Exposure — compact */}
      <section className="dashboard-section">
        <SectionHeader title="Live Exposure" subtitle="Open positions at a glance" />
        {exposureLoading && <LoadingSkeleton lines={2} />}
        {!exposureLoading && positions.length === 0 ? (
          <div className="grid-cards grid-cards--3">
            <KPICard title="Open Positions" value={0} />
            <KPICard title="Unrealized P&L" value="—" />
            <KPICard title="Status" value="No exposure" />
          </div>
        ) : !exposureLoading && positions.length > 0 ? (
          <>
            {orphanedCount > 0 && (
              <div className="info-note" style={{ marginBottom: '0.75rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg)' }}>
                <strong>Warning:</strong> {orphanedCount} position(s) orphaned/unmanaged. <Link to="/portfolio" className="link-mono">Review in Portfolio</Link>
              </div>
            )}
            <div className="grid-cards grid-cards--5">
              <KPICard title="Open" value={positions.length} />
              <KPICard
                title="Intraday"
                value={positions.filter(p => p.holding_period_type !== 'swing').length}
              />
              <KPICard
                title="Swing"
                value={positions.filter(p => p.holding_period_type === 'swing').length}
                subtitle={positions.filter(p => p.holding_period_type === 'swing' && p.overnight_carry).length > 0
                  ? `${positions.filter(p => p.holding_period_type === 'swing' && p.overnight_carry).length} overnight`
                  : undefined}
              />
              <KPICard
                title="Unrealized P&L"
                value={formatPnl(totalUnrealizedPl)}
                valueClass={pnlClass(totalUnrealizedPl)}
              />
              <KPICard
                title="Managed"
                value={`${positions.filter(p => p.managed_status === 'managed' || p.managed_status === 'pending').length}/${positions.length}`}
                valueClass={orphanedCount > 0 ? 'pnl--negative' : 'pnl--positive'}
              />
            </div>
            <div className="table-wrap" style={{ marginTop: '0.75rem' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Type</th>
                    <th>Qty</th>
                    <th>Status</th>
                    <th>Stop</th>
                    <th>Target</th>
                    <th>P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((pos) => (
                    <tr key={`${pos.symbol}-${pos.side}`}>
                      <td className="cell--symbol">
                        <Link to="/portfolio" className="link-mono">{pos.symbol}</Link>
                      </td>
                      <td>
                        <span className={pos.side?.toLowerCase() === 'long' ? 'signal-side signal-side--buy' : 'signal-side signal-side--sell'}>
                          {pos.side?.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span className={pos.holding_period_type === 'swing' ? 'badge badge--swing' : 'badge badge--intraday'}>
                          {pos.holding_period_type === 'swing' ? `Swing ${pos.days_held ?? 0}d` : 'Intra'}
                        </span>
                      </td>
                      <td>{pos.qty}</td>
                      <td><ManagedStatusBadge status={pos.managed_status} /></td>
                      <td>{pos.stop_price != null ? formatMoney(pos.stop_price) : '—'}</td>
                      <td>{pos.target_price != null ? formatMoney(pos.target_price) : '—'}</td>
                      <td className={pos.unrealized_pl != null ? pnlClass(pos.unrealized_pl) : ''}>
                        {pos.unrealized_pl != null ? formatPnl(pos.unrealized_pl) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: '0.5rem', textAlign: 'center' }}>
              <Link to="/portfolio" className="link-mono" style={{ fontSize: '0.9rem' }}>
                Full lifecycle, protection, and sizing detail in Portfolio
              </Link>
            </div>
          </>
        ) : null}
      </section>

      {/* System & Platform Status */}
      <section className="dashboard-section">
        <SectionHeader title="Platform Status" subtitle="System health, session, and pipeline readiness" />
        <div className="grid-cards grid-cards--5">
          <div className={`kpi-card kpi-card--status ${apiOk ? 'kpi-card--ok' : 'kpi-card--err'}`}>
            <div className="kpi-card__title">API</div>
            <div className="kpi-card__value">
              <StateBadge label={apiOk ? 'OK' : 'DOWN'} variant={apiOk ? 'success' : 'error'} />
            </div>
          </div>
          <KPICard
            title="Session"
            value={formatSession(sessionInfo?.session)}
            subtitle={sessionInfo?.session ? 'Market session' : undefined}
          />
          <KPICard
            title="Strategies"
            value={`${enabledStrategies.length} active`}
            subtitle={swingStrategies.length > 0 ? `${swingStrategies.length} swing lane` : 'All intraday'}
          />
          <KPICard
            title="Scanner"
            value={
              opportunitiesSummary?.scanner_session_allowed === false
                ? 'Blocked'
                : (scannerSummary?.top_count ?? 0) > 0
                  ? 'Live'
                  : 'Empty'
            }
            valueClass={
              opportunitiesSummary?.scanner_session_allowed === false
                ? 'pnl--negative'
                : (scannerSummary?.top_count ?? 0) > 0
                  ? 'pnl--positive'
                  : ''
            }
            subtitle={
              scannerSummary?.last_run_ts
                ? `Last: ${formatDateTime(scannerSummary.last_run_ts)}`
                : 'No runs yet'
            }
          />
          <KPICard
            title="AI Referee"
            value={runtimeStatus?.ai_referee?.enabled ? 'Enabled' : 'Off'}
            valueClass={runtimeStatus?.ai_referee?.enabled ? 'pnl--positive' : ''}
            subtitle={runtimeStatus?.ai_referee?.mode ?? '—'}
          />
        </div>
        <div className="grid-cards grid-cards--4" style={{ marginTop: '0.75rem' }}>
          <KPICard
            title="Focus Symbols"
            value={opportunities?.opportunities?.length ?? 0}
            subtitle={opportunitiesSummary?.source ? `From ${opportunitiesSummary.source}` : undefined}
          />
          <KPICard
            title="Fresh Intelligence"
            value={String(intelligenceSummary?.fresh_count ?? 0)}
            valueClass={(Number(intelligenceSummary?.fresh_count ?? 0)) > 0 ? 'pnl--positive' : ''}
            subtitle={
              (intelligenceSummary?.symbols_with_snapshot != null && intelligenceSummary.symbols_with_snapshot > 0)
                ? `${intelligenceSummary.symbols_with_snapshot} symbols covered`
                : undefined
            }
          />
          <KPICard
            title="Scrappy Auto"
            value={scrappyStatus?.scrappy_auto_enabled ? 'On' : 'Off'}
            valueClass={scrappyStatus?.scrappy_auto_enabled ? 'pnl--positive' : ''}
            subtitle={
              scrappyStatus?.last_run_at
                ? `Last: ${formatDateTime(scrappyStatus.last_run_at)}`
                : 'Not run yet'
            }
          />
          {rejectionSummary?.top_rejection_reasons && rejectionSummary.top_rejection_reasons.length > 0 ? (
            <KPICard
              title="Top Rejection"
              value={rejectionSummary.top_rejection_reasons[0]?.[1] ?? 0}
              subtitle={
                rejectionSummary.top_rejection_reasons[0]?.[0] === 'outside_entry_window'
                  ? `Outside entry window (${rejectionSummary.entry_window || '—'})`
                  : `${rejectionSummary.top_rejection_reasons[0]?.[0]}`
              }
              valueClass="pnl--negative"
            />
          ) : (
            <KPICard title="Rejections" value={0} subtitle="No recent rejections" />
          )}
        </div>
        <div style={{ marginTop: '0.5rem', display: 'flex', gap: '1.5rem', justifyContent: 'center' }}>
          <Link to="/system-health" className="link-mono" style={{ fontSize: '0.85rem' }}>System Health</Link>
          <Link to="/intelligence" className="link-mono" style={{ fontSize: '0.85rem' }}>Premarket Prep</Link>
          <Link to="/signals" className="link-mono" style={{ fontSize: '0.85rem' }}>Live Signals</Link>
        </div>
      </section>

      {/* Top Opportunities — compact top 8 */}
      <section className="dashboard-section">
        <SectionHeader title="Top Opportunities" subtitle="Scanner-ranked candidates — full detail in Premarket Prep" />
        {opportunitiesError && (
          <BackendNotConnected message="Scanner/opportunities endpoint unavailable" detail="Check API and scanner service." />
        )}
        {!opportunitiesError && opportunitiesLoading && <LoadingSkeleton lines={3} />}
        {!opportunitiesError && !opportunitiesLoading && (!opportunities?.opportunities?.length ? (
          <EmptyState
            message={
              opportunitiesSummary?.reason_if_blocked
                ? `Session blocked: ${opportunitiesSummary.reason_if_blocked}`
                : 'No live opportunities. Check Premarket Prep for details.'
            }
            icon="🔍"
          />
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Symbol</th>
                    <th>Score</th>
                    <th>Price</th>
                    <th>Gap %</th>
                    <th>Spread</th>
                    <th>Research</th>
                    <th>Strategy Eligible</th>
                  </tr>
                </thead>
                <tbody>
                  {(opportunities?.opportunities ?? []).slice(0, 8).map((opp) => {
                    const strategyEligibility = opp.strategy_eligibility || {};
                    const eligibleStrategies = Object.entries(strategyEligibility)
                      .filter(([, info]) => info?.eligible)
                      .map(([id]) => id);
                    return (
                      <tr key={opp.symbol}>
                        <td>{opp.rank}</td>
                        <td>
                          <Link to={`/scanner/symbol/${opp.symbol}`} className="link-mono">{opp.symbol}</Link>
                        </td>
                        <td>{opp.total_score != null ? Number(opp.total_score).toFixed(1) : '—'}</td>
                        <td>{opp.price != null ? `$${Number(opp.price).toFixed(2)}` : '—'}</td>
                        <td>{opp.gap_pct != null ? `${Number(opp.gap_pct).toFixed(1)}%` : '—'}</td>
                        <td>{opp.spread_bps != null ? `${opp.spread_bps}bp` : '—'}</td>
                        <td>
                          {opp.scrappy_present ? (
                            <span className="badge badge--green">
                              {opp.scrappy_catalyst_direction ?? 'yes'}
                            </span>
                          ) : (
                            <span className="badge badge--dim">none</span>
                          )}
                        </td>
                        <td className="cell--small">
                          {eligibleStrategies.length > 0 ? (
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.2rem' }}>
                              {eligibleStrategies.map((id) => {
                                const info = strategyEligibility[id];
                                const isSwing = info?.holding_period_type === 'swing';
                                return (
                                  <span key={id} className={isSwing ? 'badge badge--swing' : 'badge badge--success'}>
                                    {id.replace('_', ' ').slice(0, 12)}
                                  </span>
                                );
                              })}
                            </div>
                          ) : (
                            <span className="badge badge--dim">none</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {(opportunities?.opportunities?.length ?? 0) > 8 && (
              <p className="muted-text" style={{ marginTop: '0.4rem', textAlign: 'center', fontSize: '0.85rem' }}>
                Showing 8 of {opportunities?.opportunities?.length}
              </p>
            )}
            <div style={{ marginTop: '0.5rem', textAlign: 'center' }}>
              <Link to="/intelligence" className="link-mono" style={{ fontSize: '0.9rem' }}>
                Full focus board with intelligence coverage in Premarket Prep
              </Link>
            </div>
          </>
        ))}
        {!opportunitiesError && opportunities?.updated_at && (
          <p className="muted-text" style={{ marginTop: '0.4rem', fontSize: '0.8rem' }}>
            Updated {formatDateTime(opportunities.updated_at)}
          </p>
        )}
      </section>
    </div>
  );
}
