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
import { ProtectionModeBadge } from '../components/shared/ProtectionModeBadge';
import { SourceBadge } from '../components/shared/SourceBadge';
import { formatDateTime, formatSession, formatPnl } from '../utils/format';

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

      <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-success)' }}>
        <strong>Automation:</strong> Scanner, Scrappy, opportunity engine, and strategy worker run on their own schedules. Manual triggers in Premarket Prep and Strategy Lab are for testing and research only.
      </div>

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
                  <th>Note</th>
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
                    <td style={{ fontSize: '0.75rem' }}>{s.note ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Premarket Prep Summary */}
      <section className="dashboard-section">
        <SectionHeader
          title="Premarket Prep Summary"
          subtitle="Current preparation status — see Premarket Prep for full focus board"
        />
        <div className="grid-cards grid-cards--5">
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
            title="Scanner Status"
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
          {/* PHASE 5: Rejection visibility */}
          {rejectionSummary && rejectionSummary.top_rejection_reasons && rejectionSummary.top_rejection_reasons.length > 0 && (
            <KPICard
              title="Recent Rejections"
              value={rejectionSummary.top_rejection_reasons[0]?.[1] ?? 0}
              subtitle={
                rejectionSummary.top_rejection_reasons[0]?.[0] === 'outside_entry_window'
                  ? `Outside entry window (${rejectionSummary.entry_window || '09:35-11:30 ET'})`
                  : `Top: ${rejectionSummary.top_rejection_reasons[0]?.[0]}`
              }
              valueClass="pnl--negative"
            />
          )}
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
          <KPICard
            title="AI Referee"
            value={runtimeStatus?.ai_referee?.enabled ? 'Enabled' : 'Disabled'}
            valueClass={runtimeStatus?.ai_referee?.enabled ? 'pnl--positive' : ''}
            subtitle={runtimeStatus?.ai_referee?.mode ?? '—'}
          />
        </div>
        <div style={{ marginTop: '0.5rem', textAlign: 'center' }}>
          <Link to="/intelligence" className="link-mono" style={{ fontSize: '0.9rem' }}>
            → Full premarket prep board
          </Link>
        </div>
      </section>

      <section className="dashboard-section">
        <SectionHeader title="Live Paper Exposure" subtitle="Current positions with full lifecycle detail" />
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
            <div className="grid-cards grid-cards--5">
              <KPICard title="Open Positions" value={paperExposure.positions.length} />
              <KPICard 
                title="Intraday"
                value={paperExposure.positions.filter(p => p.holding_period_type !== 'swing').length}
              />
              <KPICard 
                title="Swing (Overnight)"
                value={paperExposure.positions.filter(p => p.holding_period_type === 'swing').length}
                valueClass={paperExposure.positions.some(p => p.holding_period_type === 'swing') ? 'pnl--positive' : ''}
                subtitle={paperExposure.positions.filter(p => p.holding_period_type === 'swing').length > 0
                  ? `${paperExposure.positions.filter(p => p.holding_period_type === 'swing' && p.overnight_carry).length} carrying overnight`
                  : undefined}
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
            <div className="table-wrap" style={{ marginTop: '1rem' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Type</th>
                    <th>Qty</th>
                    <th>Source</th>
                    <th>Managed</th>
                    <th>Stop</th>
                    <th>Target</th>
                    <th>Protection</th>
                    <th>P&L</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {paperExposure.positions.map((pos) => (
                    <tr key={`${pos.symbol}-${pos.side}`}>
                      <td className="cell--symbol">{pos.symbol}</td>
                      <td>
                        <span className={pos.side?.toLowerCase() === 'long' ? 'signal-side signal-side--buy' : 'signal-side signal-side--sell'}>
                          {pos.side?.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <span className={pos.holding_period_type === 'swing' ? 'badge badge--swing' : 'badge badge--intraday'}>
                          {pos.holding_period_type === 'swing' ? `Swing ${pos.days_held ?? 0}d/${pos.max_hold_days ?? 5}d` : 'Intraday'}
                        </span>
                      </td>
                      <td>{pos.qty}</td>
                      <td><SourceBadge source={pos.source} /></td>
                      <td><ManagedStatusBadge status={pos.managed_status} /></td>
                      <td>{pos.stop_price != null ? formatMoney(pos.stop_price) : '—'}</td>
                      <td>{pos.target_price != null ? formatMoney(pos.target_price) : '—'}</td>
                      <td>
                        <ProtectionModeBadge mode={pos.protection_mode} active={pos.protection_active} />
                      </td>
                      <td className={pos.unrealized_pl != null ? (pos.unrealized_pl >= 0 ? 'pnl--positive' : 'pnl--negative') : ''}>
                        {pos.unrealized_pl != null ? formatPnl(pos.unrealized_pl) : '—'}
                      </td>
                      <td>
                        {pos.signal_uuid && (
                          <Link to={`/signals/${pos.signal_uuid}`} className="link-mono" style={{ fontSize: '0.75rem' }}>
                            Signal →
                          </Link>
                        )}
                        {pos.entry_order_id && (
                          <Link to={`/orders`} className="link-mono" style={{ fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                            Order →
                          </Link>
                        )}
                        <Link to="/portfolio" className="link-mono" style={{ fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                          Full detail →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: '1rem', textAlign: 'center' }}>
              <Link to="/portfolio" className="link-mono" style={{ fontSize: '1rem', fontWeight: 500 }}>
                → View complete lifecycle in Portfolio
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
            title="Strategies"
            value={`${enabledStrategies.length} active`}
            subtitle={swingStrategies.length > 0 ? `${swingStrategies.length} swing` : undefined}
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
                    <th>Strategy Eligibility</th>
                    <th>Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {(opportunities?.opportunities ?? []).map((opp) => {
                    const strategyEligibility = opp.strategy_eligibility || {};
                    const eligibleStrategies = Object.entries(strategyEligibility)
                      .filter(([_, info]) => info?.eligible)
                      .map(([id, _]) => id);
                    const ineligibleStrategies = Object.entries(strategyEligibility)
                      .filter(([_, info]) => !info?.eligible && info?.enabled)
                      .map(([id, info]) => ({ id, reason: info?.reason }));
                    return (
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
                        <td className="cell--small">
                          {Object.keys(strategyEligibility).length > 0 ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', fontSize: '0.75rem' }}>
                              {eligibleStrategies.length > 0 && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                                  {eligibleStrategies.map((id) => {
                                    const info = strategyEligibility[id];
                                    const isSwing = info?.holding_period_type === 'swing';
                                    return (
                                      <span key={id} className={isSwing ? 'badge badge--swing' : 'badge badge--success'}>
                                        ✓ {id} {isSwing ? '(swing)' : ''}
                                      </span>
                                    );
                                  })}
                                </div>
                              )}
                              {ineligibleStrategies.length > 0 && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
                                  {ineligibleStrategies.slice(0, 3).map(({ id, reason }) => (
                                    <div key={id} className="muted-text" title={reason || ''}>
                                      {id}: {reason || '—'}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
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
                    );
                  })}
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
