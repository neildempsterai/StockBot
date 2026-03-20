import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type {
  ConfigResponse,
  HealthDetailResponse,
  HealthResponse,
  MetricsSummaryResponse,
  StrategiesResponse,
  OpportunitiesNowResponse,
  OpportunitiesSummaryResponse,
  OpportunitiesSessionResponse,
  ScannerSummaryResponse,
  ScannerRunsResponse,
  ScrappyStatusResponse,
  PaperTestProofResponse,
  PaperExposureResponse,
  PaperAccountResponse,
  PaperPositionsResponse,
  PaperOrdersResponse,
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
import { IntelligenceBadge } from '../components/shared/IntelligenceBadge';
import { LifecycleStatusBadge } from '../components/shared/LifecycleStatusBadge';
import { SizingSummary } from '../components/shared/SizingSummary';
import { formatPnl, formatDateTime, formatSession, formatTs } from '../utils/format';

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
  const { data: scannerSummary, isLoading: scannerSummaryLoading } = useQuery({
    queryKey: ['scannerSummary'],
    queryFn: () => apiGet<ScannerSummaryResponse>(ENDPOINTS.scannerSummary),
    refetchInterval: 30_000,
  });
  const { data: scannerRuns } = useQuery({
    queryKey: ['scannerRuns'],
    queryFn: () => apiGet<ScannerRunsResponse>(ENDPOINTS.scannerRuns),
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
  const { data: scrappyStatus } = useQuery({
    queryKey: ['scrappyStatus'],
    queryFn: () => apiGet<ScrappyStatusResponse>(ENDPOINTS.scrappyStatus),
    refetchInterval: 30_000,
  });
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: () => apiGet<ConfigResponse>(ENDPOINTS.config),
    refetchInterval: 60_000,
  });
  const { data: healthDetail } = useQuery({
    queryKey: ['healthDetail'],
    queryFn: () => apiGet<HealthDetailResponse>(ENDPOINTS.healthDetail),
    refetchInterval: 30_000,
  });
  const { data: paperTestProof } = useQuery({
    queryKey: ['paperTestProof'],
    queryFn: () => apiGet<PaperTestProofResponse>(ENDPOINTS.paperTestProof),
    refetchInterval: 30_000,
  });
  const { data: paperExposure, isLoading: exposureLoading } = useQuery({
    queryKey: ['paperExposure'],
    queryFn: () => apiGet<PaperExposureResponse>(ENDPOINTS.paperExposure),
    refetchInterval: 15_000,
  });
  const { data: paperAccount } = useQuery({
    queryKey: ['paperAccount'],
    queryFn: () => apiGet<PaperAccountResponse>(ENDPOINTS.account),
    refetchInterval: 30_000,
    retry: false,
  });
  const { data: paperPositions } = useQuery({
    queryKey: ['paperPositions'],
    queryFn: () => apiGet<PaperPositionsResponse>(ENDPOINTS.positions),
    refetchInterval: 30_000,
    enabled: !!paperAccount,
    retry: false,
  });
  const { data: paperOrders } = useQuery({
    queryKey: ['paperOrdersClosed'],
    queryFn: () => apiGet<PaperOrdersResponse>(`${ENDPOINTS.orders}?status=closed&limit=100`),
    refetchInterval: 30_000,
    enabled: !!paperAccount,
    retry: false,
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
  const pnl = metrics?.total_net_pnl_shadow ?? null;

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
        <SectionHeader title="Live Paper Exposure" subtitle="Current paper positions with lifecycle truth" />
        {exposureLoading && <LoadingSkeleton lines={3} />}
        {!exposureLoading && (!paperExposure?.positions || paperExposure.positions.length === 0) ? (
          <EmptyState message="No open paper positions." icon="📊" />
        ) : !exposureLoading && paperExposure?.positions ? (
          <>
            {paperExposure.positions.some((p) => p.orphaned || p.managed_status === 'orphaned' || p.managed_status === 'unmanaged') && (
              <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
                <strong>⚠ Warning:</strong> Some positions are unmanaged or orphaned. Review exit plans and protection status below.
              </div>
            )}
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Source</th>
                    <th>Managed</th>
                    <th>Lifecycle</th>
                    <th>Stop</th>
                    <th>Target</th>
                    <th>Force-Flat</th>
                    <th>Protection</th>
                    <th>Exit Order</th>
                    <th>Intelligence</th>
                    <th>Sizing</th>
                    <th>Entry</th>
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
                      <td>{pos.qty}</td>
                      <td><SourceBadge source={pos.source} /></td>
                      <td><ManagedStatusBadge status={pos.managed_status} /></td>
                      <td><LifecycleStatusBadge status={pos.lifecycle_status} /></td>
                      <td>{pos.stop_price != null ? `$${Number(pos.stop_price).toFixed(2)}` : '—'}</td>
                      <td>{pos.target_price != null ? `$${Number(pos.target_price).toFixed(2)}` : '—'}</td>
                      <td>{pos.force_flat_time ?? '—'}</td>
                      <td>
                        <ProtectionModeBadge mode={pos.protection_mode} active={pos.protection_active} />
                      </td>
                      <td>
                        {pos.exit_order_id ? (
                          <Link to={`/orders/${pos.exit_order_id}`} className="link-mono" style={{ fontSize: '0.85rem' }}>
                            {pos.exit_order_id.slice(0, 12)}…
                          </Link>
                        ) : (
                          <span className="muted-text">—</span>
                        )}
                      </td>
                      <td>
                        <IntelligenceBadge
                          scrappy={pos.scrappy_at_entry ? { present: true, stale: pos.scrappy_detail?.stale_flag, conflict: pos.scrappy_detail?.conflict_flag } : false}
                          aiReferee={pos.ai_referee_at_entry ? { ran: pos.ai_referee_detail?.ran } : false}
                          compact
                        />
                      </td>
                      <td><SizingSummary sizing={pos.sizing_at_entry} compact /></td>
                      <td className="cell--ts">{pos.entry_ts ? formatTs(pos.entry_ts) : '—'}</td>
                      <td>
                        {pos.signal_uuid && (
                          <Link to={`/signals/${pos.signal_uuid}`} className="link-mono" style={{ fontSize: '0.85rem' }}>
                            Signal
                          </Link>
                        )}
                        {pos.entry_order_id && (
                          <span className="muted-text" style={{ fontSize: '0.75rem', display: 'block' }}>
                            Order: {pos.entry_order_id.slice(0, 12)}…
                          </span>
                        )}
                        {pos.static_fallback_at_entry && (
                          <span className="flag-badge flag-badge--warn" style={{ fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                            Static fallback
                          </span>
                        )}
                        {pos.last_error && (
                          <span className="muted-text" style={{ fontSize: '0.75rem', color: 'var(--color-error)', display: 'block', marginTop: '0.25rem' }}>
                            Error: {pos.last_error.slice(0, 40)}…
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : null}
      </section>

      <section className="dashboard-section">
        <SectionHeader title="System Status" />
        <div className="grid-cards grid-cards--4">
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
          <KPICard title="Mode" value={strategy?.mode ?? '—'} />
          <KPICard
            title="Session"
            value={formatSession(sessionInfo?.session)}
            subtitle={sessionInfo?.session ? 'Current session' : undefined}
          />
        </div>
      </section>

      <section className="dashboard-section">
        <SectionHeader title="Real Paper Trading" subtitle="Actual broker positions and orders (Alpaca)" />
        {paperAccount ? (
          <>
            <div className="grid-cards grid-cards--5">
              <KPICard title="Equity" value={paperAccount.equity ? `$${parseFloat(String(paperAccount.equity)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'} />
              <KPICard title="Cash" value={paperAccount.cash ? `$${parseFloat(String(paperAccount.cash)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'} />
              <KPICard title="Open Positions" value={paperPositions?.positions?.length ?? 0} />
              <KPICard title="Closed Orders" value={paperOrders?.count ?? paperOrders?.orders?.length ?? 0} />
              <KPICard 
                title="Portfolio Value" 
                value={paperAccount.portfolio_value ? `$${parseFloat(String(paperAccount.portfolio_value)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'} 
              />
            </div>
            {paperPositions && paperPositions.positions && paperPositions.positions.length > 0 && (
              <p className="muted-text" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
                {paperPositions.positions.length} open position(s). See "Live Paper Exposure" above for details.
              </p>
            )}
          </>
        ) : (
          <EmptyState message="Paper account not configured or unavailable" icon="📊" />
        )}
      </section>

      <section className="dashboard-section">
        <SectionHeader title="Shadow Trading (Simulation)" subtitle="Internal strategy simulation — NOT real trades" />
        <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-warning)', backgroundColor: 'var(--color-warning-bg, #2d2b1b)' }}>
          <strong>⚠ Shadow vs Paper:</strong> Shadow is internal simulation for strategy validation. Paper is real broker trades. These are separate systems.
        </div>
        <div className={`grid-cards ${(metrics?.signals_with_scrappy_snapshot != null || metrics?.signals_without_scrappy_snapshot != null) ? 'grid-cards--5' : 'grid-cards--3'}`}>
          <KPICard title="Signals (total)" value={metrics?.signals_total ?? '—'} />
          <KPICard title="Shadow trades" value={metrics?.shadow_trades_total ?? '—'} variant="shadow" />
          <KPICard
            title="Net P&L (shadow)"
            value={pnl != null ? formatPnl(pnl) : '—'}
            variant="shadow"
            valueClass={pnl != null ? (pnl >= 0 ? 'pnl--positive' : 'pnl--negative') : ''}
          />
          {metrics?.signals_with_scrappy_snapshot != null && (
            <KPICard title="With Scrappy snapshot" value={metrics.signals_with_scrappy_snapshot} />
          )}
          {metrics?.signals_without_scrappy_snapshot != null && (
            <KPICard title="Without Scrappy snapshot" value={metrics.signals_without_scrappy_snapshot} />
          )}
        </div>
        {(metrics?.shadow_trades_total === 0 && metrics?.signals_total === 0) && (
          <p className="muted-text" style={{ marginTop: '0.5rem' }}>
            No qualifying trades yet. Opportunities are visible above when scanner/opportunity engine run.
          </p>
        )}
      </section>

      {config && (
        <section className="dashboard-section">
          <SectionHeader title="Execution & modes" subtitle="Deterministic strategy is sole trade authority" />
          <div className="grid-cards grid-cards--4">
            <KPICard title="Execution mode" value={config.EXECUTION_MODE ?? '—'} />
            <KPICard title="Scrappy mode" value={config.SCRAPPY_MODE ?? '—'} />
            <KPICard title="AI referee" value={config.AI_REFEREE_ENABLED ? 'Enabled' : 'Off'} />
            <KPICard title="Paper execution" value={config.PAPER_EXECUTION_ENABLED ? 'On' : 'Off'} />
          </div>
        </section>
      )}

      <section className="dashboard-section">
        <SectionHeader title="Paper test proof" subtitle="Last operator-test order per flow — proves all four flows ran and are persisted" />
        <div className="grid-cards grid-cards--4">
          {(paperTestProof?.intents ?? ['buy_open', 'sell_close', 'short_open', 'buy_cover']).map((intent) => {
            const entry = paperTestProof?.proof?.[intent];
            const label = intent.replace(/_/g, ' ');
            return (
              <div key={intent} className={`kpi-card ${entry ? 'kpi-card--ok' : ''}`}>
                <div className="kpi-card__title">{label}</div>
                <div className="kpi-card__value">
                  {entry ? (
                    <>
                      <StateBadge label={entry.status ?? '—'} variant={entry.status === 'filled' ? 'success' : entry.status === 'accepted' || entry.status === 'new' ? 'default' : 'warning'} />
                      <span className="muted-text" style={{ display: 'block', marginTop: '0.25rem', fontSize: '0.85rem' }}>
                        {entry.symbol} {entry.side} {entry.qty != null ? entry.qty : ''}
                      </span>
                      {entry.order_id && (
                        <span className="muted-text" style={{ display: 'block', fontSize: '0.75rem' }} title={entry.order_id}>
                          {entry.order_id.slice(0, 12)}…
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="muted-text">Not run yet</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {metrics?.scrappy_gate_rejections && Object.keys(metrics.scrappy_gate_rejections).length > 0 && (
        <section>
          <SectionHeader title="Scrappy Gate Rejections" />
          <div className="badge-row">
            {Object.entries(metrics.scrappy_gate_rejections).map(([reason, count]) => (
              <StateBadge key={reason} label={`${reason}: ${count}`} variant="warning" />
            ))}
          </div>
        </section>
      )}

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
            {(healthDetail?.gateway_fallback_reason || healthDetail?.worker_fallback_reason) && (
              <p className="muted-text" style={{ marginTop: '0.5rem' }}>
                Dynamic universe on fallback: {[healthDetail.gateway_fallback_reason, healthDetail.worker_fallback_reason].filter(Boolean).join('; ') || 'no_live_top_symbols'}
              </p>
            )}
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

      <section className="dashboard-section">
        <SectionHeader title="Scanner Status" subtitle="Last run and rejection reasons" />
        {scannerSummaryLoading && <LoadingSkeleton lines={2} />}
        {!scannerSummaryLoading && (
          <div className="grid-cards grid-cards--3">
            <KPICard
              title="Last run"
              value={scannerSummary?.last_run_ts ? formatDateTime(scannerSummary.last_run_ts) : '—'}
              subtitle={scannerSummary?.last_run_status ?? undefined}
            />
            <KPICard title="Top candidates" value={scannerSummary?.top_count ?? '—'} />
            <KPICard
              title="Universe / scored"
              value={scannerRuns?.runs?.[0] ? `${scannerRuns.runs[0].universe_size} / ${scannerRuns.runs[0].candidates_scored}` : '—'}
            />
          </div>
        )}
        {!scannerSummaryLoading && scannerSummary?.rejection_reasons && Object.keys(scannerSummary.rejection_reasons).length > 0 && (
          <div style={{ marginTop: '1rem' }}>
            <strong>Top rejection reasons</strong>
            <div className="badge-row" style={{ marginTop: '0.5rem' }}>
              {Object.entries(scannerSummary.rejection_reasons)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10)
                .map(([reason, count]) => (
                  <StateBadge key={reason} label={`${reason}: ${count}`} variant="warning" />
                ))}
            </div>
          </div>
        )}
      </section>

      <section className="dashboard-section">
        <SectionHeader title="Scrappy automation" subtitle="Proactive enrichment of top candidates" />
        <div className="grid-cards grid-cards--4">
          <KPICard
            title="Auto enabled"
            value={scrappyStatus?.scrappy_auto_enabled != null ? (scrappyStatus.scrappy_auto_enabled ? 'Yes' : 'No') : '—'}
          />
          <KPICard
            title="Last run"
            value={scrappyStatus?.last_run_at ? formatDateTime(scrappyStatus.last_run_at) : '—'}
            subtitle={scrappyStatus?.last_notes_created != null ? `${scrappyStatus.last_notes_created} notes` : undefined}
          />
          <KPICard title="Watchlist size" value={scrappyStatus?.watchlist_size ?? '—'} />
          <KPICard
            title="Dynamic universe"
            value={opportunitiesSummary?.top_count ?? healthDetail?.gateway_symbol_count ?? '—'}
            subtitle={opportunitiesSummary?.source ?? healthDetail?.gateway_symbol_source ?? undefined}
          />
          {healthDetail?.gateway_symbol_refresh_ts != null && (
            <KPICard
              title="Gateway symbol refresh"
              value={formatDateTime(healthDetail.gateway_symbol_refresh_ts)}
            />
          )}
          {scrappyStatus?.last_snapshots_updated != null && (
            <KPICard title="Last run snapshots" value={scrappyStatus.last_snapshots_updated} />
          )}
        </div>
      </section>

      {scannerRuns?.runs && scannerRuns.runs.length > 0 && (
        <section className="dashboard-section">
          <SectionHeader title="Scanner history" subtitle="Recent runs" />
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Status</th>
                  <th>Universe</th>
                  <th>Scored</th>
                  <th>Top</th>
                  <th>Session</th>
                </tr>
              </thead>
              <tbody>
                {scannerRuns.runs.slice(0, 10).map((r) => (
                  <tr key={r.run_id}>
                    <td>{r.run_ts ? formatDateTime(r.run_ts) : '—'}</td>
                    <td><StateBadge label={r.status ?? '—'} variant={r.status === 'completed' ? 'success' : 'default'} /></td>
                    <td>{r.universe_size}</td>
                    <td>{r.candidates_scored}</td>
                    <td>{r.top_candidates_count}</td>
                    <td>{r.market_session ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section>
        <SectionHeader title="Quick Links" />
        <div className="quick-links">
          <Link to="/signals" className="quick-link">⚡ Live Signals</Link>
          <Link to="/command" className="quick-link">🔍 Scanner / Opportunities</Link>
          <Link to="/shadow-trades" className="quick-link">👻 Shadow Trades</Link>
          <Link to="/performance" className="quick-link">📈 Performance</Link>
          <Link to="/intelligence" className="quick-link">🧠 Intelligence</Link>
          <Link to="/ai-referee" className="quick-link">🤖 AI Referee</Link>
          <Link to="/system-health" className="quick-link">❤️ System Health</Link>
        </div>
      </section>
    </div>
  );
}
