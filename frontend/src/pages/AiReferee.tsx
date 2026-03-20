import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { StateBadge } from '../components/shared/StateBadge';
import { KPICard } from '../components/shared/KPICard';
import { formatTs } from '../utils/format';
import type { PaperExposureResponse, RuntimeStatusResponse, OpportunitiesNowResponse } from '../types/api';

interface Assessment {
  assessment_id: string;
  symbol?: string;
  decision_class?: string;
  setup_quality_score?: number;
  plain_english_rationale?: string;
  assessment_ts?: string;
  evidence_sufficiency?: string;
  contradiction_flag?: boolean;
  stale_flag?: boolean;
  [key: string]: unknown;
}

export function AiReferee() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['aiRefereeRecent'],
    queryFn: () => apiGet<{ assessments?: Assessment[] }>(`${ENDPOINTS.aiRefereeRecent}?limit=50`),
    refetchInterval: 30_000,
  });
  const { data: runtimeStatus } = useQuery({
    queryKey: ['runtimeStatus'],
    queryFn: () => apiGet<RuntimeStatusResponse>(ENDPOINTS.runtimeStatus),
    refetchInterval: 30_000,
  });
  const { data: paperExposure } = useQuery({
    queryKey: ['paperExposure'],
    queryFn: () => apiGet<PaperExposureResponse>(ENDPOINTS.paperExposure),
    refetchInterval: 15_000,
  });
  const { data: opportunities } = useQuery({
    queryKey: ['opportunitiesNow'],
    queryFn: () => apiGet<OpportunitiesNowResponse>(ENDPOINTS.opportunitiesNow),
    refetchInterval: 30_000,
  });
  
  // Create a map of symbols with open positions
  const symbolsWithOpenPositions = new Set(
    paperExposure?.positions?.map(p => p.symbol?.toUpperCase()).filter(Boolean) ?? []
  );

  // Create maps for quick lookups
  const assessmentMap = new Map(
    (data?.assessments ?? []).map((a) => [a.symbol?.toUpperCase(), a])
  );
  const focusSymbols = opportunities?.opportunities ?? [];
  
  // Calculate coverage
  const focusWithAssessment = focusSymbols.filter((o) =>
    assessmentMap.has(o.symbol?.toUpperCase())
  ).length;
  const focusNeedingAssessment = focusSymbols.filter((o) =>
    !assessmentMap.has(o.symbol?.toUpperCase())
  ).length;

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">AI Assessments</h1>
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-stack">
        <h1 className="page-title">AI Assessments</h1>
        <BackendNotConnected message="Could not load AI referee assessments" />
      </div>
    );
  }

  const assessments = data?.assessments ?? [];
  const aiRefereeEnabled = runtimeStatus?.ai_referee?.enabled ?? false;
  const aiRefereeMode = runtimeStatus?.ai_referee?.mode ?? 'advisory';
  const paperRequired = runtimeStatus?.ai_referee?.paper_required ?? false;

  return (
    <div className="page-stack">
      <h1 className="page-title">AI Assessments</h1>
      
      {/* Mode Summary */}
      <section className="dashboard-section">
        <SectionHeader
          title="AI Referee Mode"
          subtitle="Advisory only — not order authority. Deterministic strategy remains the sole trade authority."
        />
        <div className="grid-cards grid-cards--4">
          <KPICard
            title="Status"
            value={aiRefereeEnabled ? 'Enabled' : 'Disabled'}
            valueClass={aiRefereeEnabled ? 'pnl--positive' : 'pnl--negative'}
          />
          <KPICard
            title="Mode"
            value={aiRefereeMode}
            subtitle={paperRequired ? 'Required for paper trading' : 'Advisory only'}
          />
          <KPICard
            title="Assessments"
            value={assessments.length}
            subtitle="Total assessments"
          />
          <KPICard
            title="Focus Coverage"
            value={`${focusWithAssessment}/${focusSymbols.length}`}
            subtitle={focusNeedingAssessment > 0 ? `${focusNeedingAssessment} need assessment` : 'All assessed'}
            valueClass={focusNeedingAssessment > 0 ? 'pnl--negative' : 'pnl--positive'}
          />
        </div>
        {!aiRefereeEnabled && (
          <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-warning)' }}>
            <strong>AI Referee is disabled.</strong> Enable AI_REFEREE_ENABLED in .env to use. 
            {paperRequired && ' Paper trading currently requires AI Referee.'}
          </div>
        )}
        {aiRefereeEnabled && assessments.length === 0 && (
          <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-warning)' }}>
            <strong>No assessments yet.</strong> AI Referee runs when candidates reach the assessment stage. Check focus symbols in Premarket Prep.
          </div>
        )}
      </section>

      {/* Recent Assessments */}
      <section className="dashboard-section">
        <SectionHeader
          title="Recent Assessments"
          subtitle="Latest AI Referee candidate assessments"
        />
        {assessments.length === 0 ? (
          <EmptyState
            message={
              !aiRefereeEnabled
                ? "AI Referee is disabled. Enable AI_REFEREE_ENABLED in .env to use."
                : "No referee assessments yet. Enable AI_REFEREE_ENABLED and ensure candidates reach the referee."
            }
            icon="🤖"
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Live Position</th>
                  <th>Decision</th>
                  <th>Score</th>
                  <th>Evidence</th>
                  <th>Flags</th>
                  <th>Time</th>
                  <th>Rationale</th>
                </tr>
              </thead>
              <tbody>
                {assessments.map((a) => {
                  const symbolUpper = String(a.symbol ?? '').toUpperCase();
                  const hasOpenPosition = symbolsWithOpenPositions.has(symbolUpper);
                  const position = paperExposure?.positions?.find(p => p.symbol?.toUpperCase() === symbolUpper);
                  return (
                    <tr 
                      key={a.assessment_id}
                      style={hasOpenPosition ? { backgroundColor: 'var(--color-success-bg, rgba(63, 185, 80, 0.1))' } : undefined}
                    >
                      <td className="cell--symbol">
                        {a.symbol}
                        {hasOpenPosition && position && (
                          <Link to="/portfolio" className="link-mono" style={{ fontSize: '0.75rem', display: 'block', marginTop: '0.25rem' }}>
                            View position →
                          </Link>
                        )}
                      </td>
                      <td>
                        {hasOpenPosition && position ? (
                          <div style={{ fontSize: '0.85rem' }}>
                            <StateBadge label={`${position.side?.toUpperCase()} ${position.qty}`} variant="success" />
                            <div className="muted-text" style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
                              {position.unrealized_pl != null ? (
                                <span className={position.unrealized_pl >= 0 ? 'pnl--positive' : 'pnl--negative'}>
                                  {position.unrealized_pl >= 0 ? '+' : ''}${position.unrealized_pl.toFixed(2)}
                                </span>
                              ) : '—'}
                            </div>
                          </div>
                        ) : (
                          <span className="muted-text">—</span>
                        )}
                      </td>
                      <td><span className="badge badge--dim">{a.decision_class ?? '—'}</span></td>
                      <td>{a.setup_quality_score != null ? Number(a.setup_quality_score).toFixed(2) : '—'}</td>
                      <td>{a.evidence_sufficiency ?? '—'}</td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                          {a.contradiction_flag && <span className="flag-badge flag-badge--warn">contradiction</span>}
                          {a.stale_flag && <span className="flag-badge flag-badge--warn">stale</span>}
                          {!a.contradiction_flag && !a.stale_flag && <span className="flag-badge flag-badge--ok">clear</span>}
                        </div>
                      </td>
                      <td className="cell--ts">{formatTs(a.assessment_ts)}</td>
                      <td className="cell--muted" style={{ maxWidth: 400 }}>
                        {(a.plain_english_rationale ?? '').slice(0, 150)}
                        {(a.plain_english_rationale ?? '').length > 150 ? '…' : ''}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Premarket Top Candidates Needing Assessment */}
      {focusSymbols.length > 0 && (
        <section className="dashboard-section">
          <SectionHeader
            title="Focus Symbols Needing Assessment"
            subtitle="Current focus symbols without AI Referee assessment"
          />
          {focusNeedingAssessment === 0 ? (
            <EmptyState
              message="All focus symbols have been assessed."
              icon="✓"
            />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Symbol</th>
                    <th>Score</th>
                    <th>Scrappy</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {focusSymbols
                    .filter((o) => !assessmentMap.has(o.symbol?.toUpperCase()))
                    .slice(0, 20)
                    .map((opp) => (
                      <tr key={opp.symbol}>
                        <td>{opp.rank ?? '—'}</td>
                        <td className="cell--symbol">{opp.symbol}</td>
                        <td>{opp.total_score != null ? Number(opp.total_score).toFixed(2) : '—'}</td>
                        <td>
                          {opp.scrappy_present ? (
                            <span className="badge badge--dim">{opp.scrappy_catalyst_direction ?? 'present'}</span>
                          ) : (
                            <span className="muted-text">No snapshot</span>
                          )}
                        </td>
                        <td>
                          <StateBadge label="Needs assessment" variant="error" />
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
