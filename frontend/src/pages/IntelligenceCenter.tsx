import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet, apiPost } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type {
  IntelligenceRecentResponse,
  ScrappyStatusResponse,
  ScrappyAutoRunsResponse,
  RuntimeStatusResponse,
  PaperExposureResponse,
  OpportunitiesNowResponse,
  OpportunitiesSummaryResponse,
  OpportunitiesSessionResponse,
  ScannerSummaryResponse,
  PaperArmingPrerequisitesResponse,
} from '../types/api';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { KPICard } from '../components/shared/KPICard';
import { RefreshBadge } from '../components/shared/RefreshBadge';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { StateBadge } from '../components/shared/StateBadge';
import { formatTs, formatSession } from '../utils/format';

interface AiRefereeAssessment {
  assessment_id: string;
  symbol?: string;
  decision_class?: string;
  setup_quality_score?: number;
  plain_english_rationale?: string;
  assessment_ts?: string;
  [key: string]: unknown;
}

export function IntelligenceCenter() {
  const queryClient = useQueryClient();
  
  // Premarket readiness data
  const { data: sessionInfo } = useQuery({
    queryKey: ['opportunitiesSession'],
    queryFn: () => apiGet<OpportunitiesSessionResponse>(ENDPOINTS.opportunitiesSession),
    refetchInterval: 60_000,
  });
  const { data: opportunitiesSummary } = useQuery({
    queryKey: ['opportunitiesSummary'],
    queryFn: () => apiGet<OpportunitiesSummaryResponse>(ENDPOINTS.opportunitiesSummary),
    refetchInterval: 30_000,
  });
  const { data: scannerSummary } = useQuery({
    queryKey: ['scannerSummary'],
    queryFn: () => apiGet<ScannerSummaryResponse>(ENDPOINTS.scannerSummary),
    refetchInterval: 30_000,
  });
  const { data: scrappyStatus } = useQuery({
    queryKey: ['scrappyStatus'],
    queryFn: () => apiGet<ScrappyStatusResponse>(ENDPOINTS.scrappyStatus),
    refetchInterval: 30_000,
  });
  const { data: runtimeStatus } = useQuery({
    queryKey: ['runtimeStatus'],
    queryFn: () => apiGet<RuntimeStatusResponse>(ENDPOINTS.runtimeStatus),
    refetchInterval: 30_000,
  });
  const { data: prerequisites } = useQuery({
    queryKey: ['paperArmingPrerequisites'],
    queryFn: () => apiGet<PaperArmingPrerequisitesResponse>(ENDPOINTS.paperArmingPrerequisites),
    refetchInterval: 30_000,
  });
  
  // Focus board data
  const { data: opportunities, isLoading: opportunitiesLoading, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['opportunitiesNow'],
    queryFn: () => apiGet<OpportunitiesNowResponse>(ENDPOINTS.opportunitiesNow),
    refetchInterval: 30_000,
  });
  const { data: recent, isLoading: recentLoading } = useQuery({
    queryKey: ['intelligenceRecent'],
    queryFn: () => apiGet<IntelligenceRecentResponse>(`${ENDPOINTS.intelligenceRecent}?limit=50`),
    refetchInterval: 30_000,
  });
  const { data: aiRefereeRecent } = useQuery({
    queryKey: ['aiRefereeRecent'],
    queryFn: () => apiGet<{ assessments?: AiRefereeAssessment[] }>(`${ENDPOINTS.aiRefereeRecent}?limit=50`),
    refetchInterval: 30_000,
  });
  const { data: paperExposure } = useQuery({
    queryKey: ['paperExposure'],
    queryFn: () => apiGet<PaperExposureResponse>(ENDPOINTS.paperExposure),
    refetchInterval: 15_000,
  });
  const { data: autoRuns } = useQuery({
    queryKey: ['scrappyAutoRuns'],
    queryFn: () => apiGet<ScrappyAutoRunsResponse>(`${ENDPOINTS.scrappyAutoRuns}?limit=5`),
    refetchInterval: 30_000,
  });

  // Manual run mutations
  const runScrappyMutation = useMutation({
    mutationFn: () =>
      apiPost<{ run_id?: string; outcome_code?: string; notes_created?: number; run_type?: string }>(
        ENDPOINTS.scrappyRun,
        { run_type: 'sweep' }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['intelligenceRecent'] });
      queryClient.invalidateQueries({ queryKey: ['scrappyStatus'] });
      queryClient.invalidateQueries({ queryKey: ['scrappyAutoRuns'] });
    },
  });
  const runWatchlistMutation = useMutation({
    mutationFn: () =>
      apiPost<{ run_id?: string; outcome_code?: string; notes_created?: number; run_type?: string }>(
        ENDPOINTS.scrappyRunWatchlist
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['intelligenceRecent'] });
      queryClient.invalidateQueries({ queryKey: ['scrappyStatus'] });
      queryClient.invalidateQueries({ queryKey: ['scrappyAutoRuns'] });
    },
  });

  const isLoading = opportunitiesLoading || recentLoading;

  // Create maps for quick lookups
  const symbolsWithOpenPositions = new Set(
    paperExposure?.positions?.map((p: { symbol?: string }) => p.symbol?.toUpperCase()).filter(Boolean) ?? []
  );
  const snapshotMap = new Map(
    (recent?.snapshots ?? []).map((s) => [s.symbol?.toUpperCase(), s])
  );
  const aiRefereeMap = new Map(
    (aiRefereeRecent?.assessments ?? []).map((a) => [a.symbol?.toUpperCase(), a])
  );

  // Calculate coverage stats
  const focusSymbols = opportunities?.opportunities ?? [];
  const symbolsWithSnapshots = new Set(
    (recent?.snapshots ?? []).map((s) => s.symbol?.toUpperCase())
  );
  const symbolsWithFreshSnapshots = new Set(
    (recent?.snapshots ?? [])
      .filter((s) => !s.stale_flag && !s.conflict_flag)
      .map((s) => s.symbol?.toUpperCase())
  );
  const symbolsWithStaleSnapshots = new Set(
    (recent?.snapshots ?? [])
      .filter((s) => s.stale_flag)
      .map((s) => s.symbol?.toUpperCase())
  );
  const symbolsWithConflictedSnapshots = new Set(
    (recent?.snapshots ?? [])
      .filter((s) => s.conflict_flag)
      .map((s) => s.symbol?.toUpperCase())
  );
  
  // intelligenceSummary is available for overall stats if needed

  const focusWithIntelligence = focusSymbols.filter((o) =>
    symbolsWithSnapshots.has(o.symbol?.toUpperCase())
  ).length;
  const focusMissingIntelligence = focusSymbols.filter((o) =>
    !symbolsWithSnapshots.has(o.symbol?.toUpperCase())
  ).length;
  const focusWithFreshIntelligence = focusSymbols.filter((o) =>
    symbolsWithFreshSnapshots.has(o.symbol?.toUpperCase())
  ).length;
  const focusWithStaleIntelligence = focusSymbols.filter((o) =>
    symbolsWithStaleSnapshots.has(o.symbol?.toUpperCase())
  ).length;
  const focusWithConflictedIntelligence = focusSymbols.filter((o) =>
    symbolsWithConflictedSnapshots.has(o.symbol?.toUpperCase())
  ).length;

  // Scanner status
  const scannerLive = scannerSummary?.last_run_status === 'completed' && (scannerSummary?.top_count ?? 0) > 0;
  const scannerBlocked = opportunitiesSummary?.scanner_session_allowed === false;
  const scannerEmpty = (scannerSummary?.top_count ?? 0) === 0 && !scannerBlocked;

  // Paper readiness
  const paperArmed = runtimeStatus?.paper_trading_armed ?? false;
  const paperBlockers = prerequisites?.blockers ?? [];
  const paperReady = prerequisites?.satisfied ?? false;

  // Dynamic universe status
  const gatewaySource = runtimeStatus?.symbol_source?.gateway?.active_source;
  const workerSource = runtimeStatus?.symbol_source?.worker?.active_source;
  const dynamicUniverseFresh = gatewaySource === 'dynamic' && workerSource !== 'static';
  const universeLastUpdated = runtimeStatus?.symbol_source?.dynamic_universe_last_updated_at;

  if (isLoading) {
    return (
      <div>
        <h1 className="page-title">Premarket Prep</h1>
        <LoadingSkeleton lines={10} />
      </div>
    );
  }

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">Premarket Prep</h1>
        <RefreshBadge dataUpdatedAt={dataUpdatedAt} isFetching={isFetching} intervalSec={30} />
      </div>

      {/* PHASE 6: Session alignment - show current session context */}
      {sessionInfo && sessionInfo.session && sessionInfo.session !== 'premarket' && (
        <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-info)' }}>
          <strong>Current session: {formatSession(sessionInfo.session)}.</strong> Premarket Prep is mainly for before the bell. 
          The platform continues to scan and research during market hours, but AI Referee premarket runner only runs during premarket.
        </div>
      )}
      
      {/* Premarket Readiness Header */}
      <section className="dashboard-section">
        <SectionHeader
          title="Premarket Readiness"
          subtitle="Platform status and preparation coverage before market open"
        />
        <div className="grid-cards grid-cards--5">
          <KPICard
            title="Session"
            value={formatSession(sessionInfo?.session)}
            subtitle={sessionInfo?.session ? 'Current market session' : undefined}
          />
          <KPICard
            title="Scanner"
            value={
              scannerBlocked
                ? 'Blocked'
                : scannerEmpty
                  ? 'Empty'
                  : scannerLive
                    ? 'Live'
                    : 'Inactive'
            }
            valueClass={
              scannerBlocked
                ? 'pnl--negative'
                : scannerLive
                  ? 'pnl--positive'
                  : ''
            }
            subtitle={
              scannerSummary?.last_run_ts
                ? `Last run: ${formatTs(scannerSummary.last_run_ts)}`
                : 'No runs yet'
            }
          />
          <KPICard
            title="Scrappy Auto"
            value={scrappyStatus?.scrappy_auto_enabled ? 'On' : 'Off'}
            valueClass={scrappyStatus?.scrappy_auto_enabled ? 'pnl--positive' : ''}
            subtitle={
              scrappyStatus?.last_run_at
                ? `Last: ${formatTs(scrappyStatus.last_run_at)}`
                : scrappyStatus?.last_attempt_at
                  ? `Last attempt: ${formatTs(scrappyStatus.last_attempt_at)}`
                  : 'Not run yet'
            }
          />
          <KPICard
            title="AI Referee"
            value={runtimeStatus?.ai_referee?.enabled ? 'Enabled' : 'Disabled'}
            valueClass={runtimeStatus?.ai_referee?.enabled ? 'pnl--positive' : ''}
            subtitle={
              runtimeStatus?.ai_referee?.enabled
                ? `${runtimeStatus.ai_referee.mode ?? 'advisory'}${runtimeStatus.ai_referee.paper_required ? ' (required)' : ''}`
                : 'Not active'
            }
          />
          <KPICard
            title="Paper Trading"
            value={paperArmed ? 'Armed' : 'Disarmed'}
            valueClass={paperArmed ? 'pnl--positive' : 'pnl--negative'}
            subtitle={runtimeStatus?.paper_armed_reason ?? 'Unknown'}
          />
        </div>
        <div className="grid-cards grid-cards--4" style={{ marginTop: '1rem' }}>
          <KPICard
            title="Universe Source"
            value={dynamicUniverseFresh ? 'Dynamic' : 'Static Fallback'}
            valueClass={dynamicUniverseFresh ? 'pnl--positive' : 'pnl--negative'}
            subtitle={
              universeLastUpdated
                ? `Updated: ${formatTs(universeLastUpdated)}`
                : 'No update timestamp'
            }
          />
          <KPICard
            title="Focus Symbols"
            value={focusSymbols.length}
            subtitle={`${opportunitiesSummary?.top_count ?? 0} from ${opportunitiesSummary?.source ?? 'unknown'}`}
          />
          <KPICard
            title="Fresh Intelligence"
            value={focusWithFreshIntelligence}
            valueClass={focusWithFreshIntelligence > 0 ? 'pnl--positive' : ''}
            subtitle={`${focusWithIntelligence} total with snapshots`}
          />
          <KPICard
            title="Missing Intelligence"
            value={focusMissingIntelligence}
            valueClass={focusMissingIntelligence > 0 ? 'pnl--negative' : ''}
            subtitle={`${focusWithStaleIntelligence} stale, ${focusWithConflictedIntelligence} conflicted`}
          />
        </div>
        {paperBlockers.length > 0 && (
          <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
            <strong>⚠ Paper Trading Blocked:</strong> {paperBlockers.join(', ')}
          </div>
        )}
        {!paperReady && paperBlockers.length === 0 && (
          <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-warning)' }}>
            <strong>⚠ Paper Trading Not Ready:</strong> Prerequisites check unavailable
          </div>
        )}
        {paperReady && (
          <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-success)' }}>
            <strong>✓ Paper Trading Ready:</strong> All prerequisites satisfied
          </div>
        )}
        
        {/* Critical Premarket Health */}
        <div style={{ marginTop: '1.5rem', padding: '1rem', backgroundColor: 'var(--color-bg-secondary, #1a1a1a)', borderRadius: '4px', border: '1px solid var(--color-border)' }}>
          <h3 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '1rem' }}>Premarket Health Status</h3>
          <div className="grid-cards grid-cards--3" style={{ marginBottom: '0.75rem' }}>
            <KPICard
              title="Scanner Last Run"
              value={scannerSummary?.last_run_ts ? formatTs(scannerSummary.last_run_ts) : 'Never'}
              valueClass={scannerLive ? 'pnl--positive' : ''}
              subtitle={scannerSummary?.last_run_status ?? '—'}
            />
            <KPICard
              title="Opportunity Last Run"
              value={opportunities?.updated_at ? formatTs(opportunities.updated_at) : 'Never'}
              subtitle={opportunitiesSummary?.source ?? '—'}
            />
            <KPICard
              title="Scrappy Last Success"
              value={scrappyStatus?.last_run_at ? formatTs(scrappyStatus.last_run_at) : 'Never'}
              valueClass={scrappyStatus?.last_run_at ? 'pnl--positive' : 'pnl--negative'}
              subtitle={
                scrappyStatus?.last_snapshots_updated != null
                  ? `${scrappyStatus.last_snapshots_updated} snapshots`
                  : undefined
              }
            />
          </div>
          {scrappyStatus?.last_failure_reason && (
            <div className="info-note" style={{ marginTop: '0.5rem', borderLeft: '3px solid var(--color-error)', backgroundColor: 'var(--color-error-bg, #2d1b1b)' }}>
              <strong>⚠ Scrappy Last Failure:</strong> {scrappyStatus.last_failure_reason}
            </div>
          )}
          {scrappyStatus?.last_symbols_requested && scrappyStatus.last_symbols_requested.length > 0 && (
            <p className="muted-text" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
              Last requested: {scrappyStatus.last_symbols_requested.slice(0, 10).join(', ')}
              {scrappyStatus.last_symbols_requested.length > 10 ? ` +${scrappyStatus.last_symbols_requested.length - 10} more` : ''}
            </p>
          )}
          <div className="grid-cards grid-cards--4" style={{ marginTop: '0.75rem' }}>
            <KPICard
              title="Focus Symbols"
              value={focusSymbols.length}
            />
            <KPICard
              title="Fresh Research"
              value={focusSymbols.filter((o) => {
                const sym = o.symbol?.toUpperCase();
                const snap = snapshotMap.get(sym);
                return snap?.coverage_status === 'fresh_research';
              }).length}
              valueClass={focusSymbols.filter((o) => {
                const sym = o.symbol?.toUpperCase();
                const snap = snapshotMap.get(sym);
                return snap?.coverage_status === 'fresh_research';
              }).length > 0 ? 'pnl--positive' : ''}
            />
            <KPICard
              title="Carried Forward"
              value={focusSymbols.filter((o) => {
                const sym = o.symbol?.toUpperCase();
                const snap = snapshotMap.get(sym);
                return snap?.coverage_status === 'carried_forward_research';
              }).length}
            />
            <KPICard
              title="Needing Research"
              value={focusSymbols.filter((o) => {
                const sym = o.symbol?.toUpperCase();
                const snap = snapshotMap.get(sym);
                return snap?.coverage_status === 'no_research' || snap?.coverage_status === 'low_evidence' || !snap;
              }).length}
              valueClass={focusSymbols.filter((o) => {
                const sym = o.symbol?.toUpperCase();
                const snap = snapshotMap.get(sym);
                return snap?.coverage_status === 'no_research' || snap?.coverage_status === 'low_evidence' || !snap;
              }).length > 0 ? 'pnl--negative' : ''}
            />
            <KPICard
              title="Assessed by AI"
              value={focusSymbols.filter((o) => aiRefereeMap.has(o.symbol?.toUpperCase())).length}
              subtitle={`${focusSymbols.length - focusSymbols.filter((o) => aiRefereeMap.has(o.symbol?.toUpperCase())).length} need assessment`}
            />
          </div>
          {/* Overall Premarket Alive Status */}
          {(() => {
            const scrappyRecent = scrappyStatus?.last_run_at && (() => {
              const lastRun = new Date(scrappyStatus.last_run_at);
              const ageMinutes = (Date.now() - lastRun.getTime()) / 60000;
              return ageMinutes < 60; // Recent if < 1 hour
            })();
            const hasFocusSymbols = focusSymbols.length > 0;
            const hasFreshResearch = focusWithFreshIntelligence > 0;
            const scannerActive = scannerLive;
            
            let aliveStatus = 'not_running';
            let aliveMessage = 'Premarket not running';
            
            if (scannerActive && hasFocusSymbols && scrappyRecent && hasFreshResearch) {
              aliveStatus = 'alive';
              aliveMessage = 'Premarket alive: Scanner active, focus symbols identified, fresh research coverage';
            } else if (scannerActive && hasFocusSymbols && (!scrappyRecent || !scrappyStatus?.last_run_at || focusWithFreshIntelligence === 0)) {
              aliveStatus = 'degraded';
              const reasons: string[] = [];
              if (!scrappyStatus?.last_run_at) {
                reasons.push('Scrappy has not run');
              } else if (!scrappyRecent) {
                reasons.push(`Scrappy last run ${Math.round((Date.now() - new Date(scrappyStatus.last_run_at).getTime()) / 60000)} minutes ago`);
              }
              if (focusWithFreshIntelligence === 0 && focusSymbols.length > 0) {
                reasons.push('No fresh research on focus symbols');
              }
              if (scrappyStatus?.last_failure_reason) {
                reasons.push(`Scrappy failure: ${scrappyStatus.last_failure_reason}`);
              }
              aliveMessage = `Premarket degraded: Scanner active but ${reasons.join(', ')}`;
            } else if (scannerActive) {
              aliveStatus = 'partial';
              aliveMessage = 'Premarket partial: Scanner active but no focus symbols or research yet';
            }
            
            return (
              <div className="info-note" style={{ marginTop: '1rem', borderLeft: `3px solid var(--color-${aliveStatus === 'alive' ? 'success' : aliveStatus === 'degraded' ? 'error' : 'warning'})`, backgroundColor: `var(--color-${aliveStatus === 'alive' ? 'success' : aliveStatus === 'degraded' ? 'error' : 'warning'}-bg, #2d2b1b)` }}>
                <strong>{aliveStatus === 'alive' ? '✓' : aliveStatus === 'degraded' ? '⚠' : '○'} {aliveMessage}</strong>
              </div>
            );
          })()}
        </div>
      </section>

      {/* Focus Board */}
      <section className="dashboard-section">
        <SectionHeader
          title="Focus Board"
          subtitle="Current scanner-ranked symbols with intelligence coverage and readiness status"
        />
        {focusSymbols.length === 0 ? (
          <EmptyState
            message={
              opportunitiesSummary?.reason_if_blocked
                ? `Scanner blocked: ${opportunitiesSummary.reason_if_blocked}`
                : opportunitiesSummary?.source === 'none' && opportunitiesSummary?.reason === 'no_live_scanner_run'
                  ? 'No live scanner run yet. Scanner may be starting or bootstrap not run.'
                  : 'No focus symbols available. Check scanner status and gateway/worker fallback reasons.'
            }
            icon="🔍"
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Symbol</th>
                  <th>Score</th>
                  <th>Source</th>
                  <th>Price</th>
                  <th>Gap %</th>
                  <th>Scrappy</th>
                  <th>AI Referee</th>
                  <th>Strategy Eligibility</th>
                  <th>Position</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {focusSymbols.map((opp) => {
                  const symbolUpper = opp.symbol?.toUpperCase();
                  const snapshot = snapshotMap.get(symbolUpper);
                  const aiAssessment = aiRefereeMap.get(symbolUpper);
                  const position = paperExposure?.positions?.find(
                    (p: { symbol?: string }) => p.symbol?.toUpperCase() === symbolUpper
                  );
                  const hasOpenPosition = symbolsWithOpenPositions.has(symbolUpper);
                  const hasIntelligence = snapshot != null;
                  const coverageStatus = snapshot?.coverage_status || (hasIntelligence ? 'low_evidence' : 'no_research');
                  const coverageReason = snapshot?.coverage_reason || '';
                  const hasFreshResearch = coverageStatus === 'fresh_research';
                  const hasCarriedForwardResearch = coverageStatus === 'carried_forward_research';
                  const hasLowEvidence = coverageStatus === 'low_evidence';
                  const hasNoResearch = coverageStatus === 'no_research';
                  const hasAiAssessment = aiAssessment != null;
                  const strategyEligibility = opp.strategy_eligibility || {};
                  const eligibleStrategies = Object.entries(strategyEligibility)
                    .filter(([_, info]) => info?.eligible)
                    .map(([id, _]) => id);
                  const ineligibleStrategies = Object.entries(strategyEligibility)
                    .filter(([_, info]) => !info?.eligible && info?.enabled)
                    .map(([id, info]) => ({ id, reason: info?.reason }));

                  // Determine pipeline stage with explicit reasoning using coverage status
                  let pipelineStage = 'discovered';
                  let stageReason = '';
                  
                  if (hasOpenPosition) {
                    pipelineStage = 'active';
                    stageReason = 'Open paper position exists';
                  } else if (hasNoResearch) {
                    pipelineStage = 'missing';
                    stageReason = coverageReason || 'No research coverage - needs research';
                  } else if (hasLowEvidence) {
                    pipelineStage = 'blocked';
                    stageReason = coverageReason || 'Low evidence - insufficient research support';
                  } else if (hasCarriedForwardResearch && !hasAiAssessment && runtimeStatus?.ai_referee?.enabled) {
                    pipelineStage = 'watch';
                    stageReason = coverageReason || 'Carried-forward research, awaiting AI assessment';
                  } else if (hasCarriedForwardResearch && hasAiAssessment) {
                    pipelineStage = 'watch';
                    stageReason = 'Carried-forward research, AI assessed';
                  } else if (hasFreshResearch && !hasAiAssessment && runtimeStatus?.ai_referee?.enabled) {
                    pipelineStage = 'researched';
                    stageReason = 'Fresh research complete, awaiting AI assessment';
                  } else if (hasFreshResearch && hasAiAssessment) {
                    pipelineStage = 'ready';
                    stageReason = 'Fresh research, AI assessed';
                  } else if (hasFreshResearch) {
                    pipelineStage = 'watch';
                    stageReason = 'Fresh research, no AI assessment yet';
                  } else {
                    pipelineStage = 'blocked';
                    stageReason = coverageReason || 'Unknown state';
                  }
                  
                  // Use pipelineStage for readinessStatus display
                  const readinessStatus = pipelineStage;

                  return (
                    <tr
                      key={opp.symbol}
                      style={hasOpenPosition ? { backgroundColor: 'var(--color-success-bg, rgba(63, 185, 80, 0.1))' } : undefined}
                    >
                      <td>{opp.rank ?? '—'}</td>
                      <td className="cell--symbol">
                        {opp.symbol}
                        {hasOpenPosition && position && (
                          <Link to="/portfolio" className="link-mono" style={{ fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                            View position →
                          </Link>
                        )}
                      </td>
                      <td>{opp.total_score != null ? Number(opp.total_score).toFixed(2) : '—'}</td>
                      <td>
                        <span className="badge badge--dim">{opp.candidate_source ?? 'scanner'}</span>
                      </td>
                      <td>{opp.price != null ? `$${Number(opp.price).toFixed(2)}` : '—'}</td>
                      <td>{opp.gap_pct != null ? `${Number(opp.gap_pct).toFixed(2)}%` : '—'}</td>
                      <td>
                        {hasIntelligence ? (
                          <div style={{ fontSize: '0.85rem' }}>
                            <div>
                              <span className="badge badge--dim">{snapshot?.catalyst_direction ?? '—'}</span>
                            </div>
                            <div style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                              {snapshot?.evidence_count ?? 0} evidence
                              {coverageStatus === 'fresh_research' && <span className="flag-badge flag-badge--success" style={{ marginLeft: '0.25rem' }}> fresh</span>}
                              {coverageStatus === 'carried_forward_research' && <span className="flag-badge flag-badge--warn" style={{ marginLeft: '0.25rem' }}> carried</span>}
                              {coverageStatus === 'low_evidence' && <span className="flag-badge flag-badge--warn" style={{ marginLeft: '0.25rem' }}> low</span>}
                              {coverageStatus === 'no_research' && <span className="flag-badge flag-badge--error" style={{ marginLeft: '0.25rem' }}> none</span>}
                            </div>
                          </div>
                        ) : (
                          <span className="muted-text">No snapshot</span>
                        )}
                      </td>
                      <td>
                        {hasAiAssessment ? (
                          <div style={{ fontSize: '0.85rem' }}>
                            <div>
                              <span className="badge badge--dim">{aiAssessment.decision_class ?? '—'}</span>
                            </div>
                            <div style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                              Score: {aiAssessment.setup_quality_score ?? '—'}
                            </div>
                          </div>
                        ) : (
                          <span className="muted-text">No assessment</span>
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
                                    <div key={id}>
                                      <span className={isSwing ? 'badge badge--swing' : 'badge badge--success'}>
                                        ✓ {id} {isSwing ? '(swing)' : ''}
                                      </span>
                                    </div>
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
                        {hasOpenPosition && position ? (
                          <div style={{ fontSize: '0.85rem' }}>
                            <StateBadge label={`${position.side?.toUpperCase()} ${position.qty}`} variant="success" />
                            {position.holding_period_type === 'swing' && (
                              <div style={{ marginTop: '0.15rem' }}>
                                <span className="badge badge--swing">Swing {position.days_held ?? 0}d/{position.max_hold_days ?? 5}d</span>
                              </div>
                            )}
                            {position.unrealized_pl != null && (
                              <div className="muted-text" style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                                <span className={position.unrealized_pl >= 0 ? 'pnl--positive' : 'pnl--negative'}>
                                  {position.unrealized_pl >= 0 ? '+' : ''}${position.unrealized_pl.toFixed(2)}
                                </span>
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="muted-text">—</span>
                        )}
                      </td>
                      <td>
                        <StateBadge
                          label={readinessStatus}
                          variant={
                            readinessStatus === 'ready' || readinessStatus === 'active'
                              ? 'success'
                              : readinessStatus === 'stale' || readinessStatus === 'missing' || readinessStatus === 'blocked'
                                ? 'error'
                              : readinessStatus === 'researched'
                                ? 'warning'
                                : 'default'
                          }
                        />
                        <div className="muted-text" style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                          {stageReason}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {opportunities?.updated_at && (
          <p className="muted-text" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
            Focus board updated: {formatTs(opportunities.updated_at)}
          </p>
        )}
      </section>

      {/* Automation Status */}
      <section className="dashboard-section">
        <SectionHeader
          title="Automation Status"
          subtitle="Scrappy and AI Referee participation in premarket preparation"
        />
        <div className="grid-cards grid-cards--4">
          <KPICard
            title="Scrappy Auto-run"
            value={scrappyStatus?.scrappy_auto_enabled ? 'On' : 'Off'}
            valueClass={scrappyStatus?.scrappy_auto_enabled ? 'pnl--positive' : ''}
          />
          <KPICard
            title="Last Scrappy Run"
            value={scrappyStatus?.last_run_at ? formatTs(scrappyStatus.last_run_at) : '—'}
            subtitle={
              scrappyStatus?.last_snapshots_updated
                ? `${scrappyStatus.last_snapshots_updated} snapshots updated`
                : undefined
            }
          />
          <KPICard
            title="AI Referee"
            value={runtimeStatus?.ai_referee?.enabled ? 'Enabled' : 'Disabled'}
            valueClass={runtimeStatus?.ai_referee?.enabled ? 'pnl--positive' : ''}
            subtitle={
              runtimeStatus?.ai_referee?.enabled
                ? `${runtimeStatus.ai_referee.mode ?? 'advisory'}${runtimeStatus.ai_referee.paper_required ? ' (required)' : ''}`
                : undefined
            }
          />
          <KPICard
            title="AI Assessments"
            value={aiRefereeRecent?.assessments?.length ?? 0}
            subtitle="Recent assessments"
          />
        </div>
        {autoRuns?.runs?.length ? (
          <p className="muted-text" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
            Recent auto-runs: {autoRuns.runs.slice(0, 3).map((r) => `${r.symbols_count ?? 0} symbols, ${r.notes_created ?? 0} notes`).join('; ')}
          </p>
        ) : null}
      </section>

      {/* Manual Controls */}
      <section className="dashboard-section">
        <SectionHeader
          title="Manual Controls (Testing Only)"
          subtitle="One-off overrides — not required for normal operation"
        />
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
          <button
            type="button"
            className="btn btn--secondary"
            disabled={runScrappyMutation.isPending}
            onClick={() => runScrappyMutation.mutate()}
          >
            {runScrappyMutation.isPending ? 'Running…' : 'Run Scrappy (sweep)'}
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            disabled={runWatchlistMutation.isPending}
            onClick={() => runWatchlistMutation.mutate()}
          >
            {runWatchlistMutation.isPending ? 'Running…' : 'Run Scrappy (watchlist)'}
          </button>
        </div>
        {(runScrappyMutation.isError || runWatchlistMutation.isError) && (
          <p className="cell--muted" style={{ color: 'var(--color-error)', marginBottom: '1rem' }}>
            Error: {(() => {
              const err = runScrappyMutation.error || runWatchlistMutation.error;
              if (err && typeof err === 'object' && 'detail' in err) return String((err as { detail?: string }).detail);
              if (err instanceof Error) return err.message;
              return 'Request failed';
            })()}
          </p>
        )}
        {(runScrappyMutation.isSuccess || runWatchlistMutation.isSuccess) && (() => {
          const data = runScrappyMutation.isSuccess ? runScrappyMutation.data : runWatchlistMutation.data;
          return (
            <div className="info-note" style={{ marginBottom: '1rem', borderLeft: '3px solid var(--color-success)' }}>
              <strong>Run completed.</strong>
              {data && (
                <>
                  {data.run_id && <> run_id: {String(data.run_id).slice(0, 16)}…</>}
                  {data.outcome_code && <> outcome: {data.outcome_code}</>}
                  {(data.notes_created ?? 0) > 0 && <> notes_created: {data.notes_created}</>}
                </>
              )}
              {' '}Refreshing snapshots…
            </div>
          );
        })()}
      </section>
    </div>
  );
}
