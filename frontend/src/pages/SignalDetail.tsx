import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SectionHeader } from '../components/shared/SectionHeader';
import { StateBadge } from '../components/shared/StateBadge';
import { ManagedStatusBadge } from '../components/shared/ManagedStatusBadge';
import { ProtectionModeBadge } from '../components/shared/ProtectionModeBadge';
import { formatTs, formatDateTime } from '../utils/format';

export function SignalDetail() {
  const { signalUuid } = useParams<{ signalUuid: string }>();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['signal', signalUuid],
    queryFn: () => apiGet<Record<string, unknown>>(ENDPOINTS.signalDetail(signalUuid!)),
    enabled: !!signalUuid,
  });

  if (!signalUuid) {
    return (
      <div className="page-stack">
        <p className="muted-text">No signal ID</p>
        <Link to="/signals">← Back to signals</Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Signal</h1>
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Signal</h1>
        <BackendNotConnected message="Could not load signal" />
        <Link to="/signals">← Back to signals</Link>
      </div>
    );
  }

  const reasonCodes = (data.reason_codes as string[]) ?? [];
  const scrappyReasonCodes = (data.scrappy_reason_codes as string[]) ?? [];
  const intelligenceSnapshot = data.intelligence_snapshot as Record<string, unknown> | undefined;
  const aiRefereeAssessment = data.ai_referee_assessment as Record<string, unknown> | undefined;
  const paperOrderId = data.paper_order_id as string | undefined;
  const executionMode = data.execution_mode as string | undefined;
  const lifecycle = data.lifecycle as {
    lifecycle_status?: string;
    entry_order_id?: string;
    exit_order_id?: string;
    stop_price?: number;
    target_price?: number;
    force_flat_time?: string;
    protection_mode?: string;
    protection_active?: boolean;
    managed_status?: string;
    universe_source?: string;
    static_fallback_at_entry?: boolean;
  } | undefined;

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">Signal {signalUuid.slice(0, 8)}…</h1>
        <Link to="/signals" className="link-mono">← Back to signals</Link>
      </div>

      <section className="dashboard-section">
        <SectionHeader title="Signal Details" />
        <div className="grid-cards grid-cards--4">
          <div>
            <div className="kpi-card__title">Symbol</div>
            <div className="kpi-card__value">{String(data.symbol ?? '—')}</div>
          </div>
          <div>
            <div className="kpi-card__title">Side</div>
            <div className="kpi-card__value">
              <span className={String(data.side ?? '').toLowerCase() === 'buy' ? 'signal-side signal-side--buy' : 'signal-side signal-side--sell'}>
                {String(data.side ?? '').toUpperCase()}
              </span>
            </div>
          </div>
          <div>
            <div className="kpi-card__title">Qty</div>
            <div className="kpi-card__value">{data.qty != null ? Number(data.qty) : '—'}</div>
          </div>
          <div>
            <div className="kpi-card__title">Strategy</div>
            <div className="kpi-card__value">
              {String(data.strategy_id ?? '—')}
              {data.strategy_version ? ` v${String(data.strategy_version)}` : ''}
            </div>
          </div>
        </div>
        <div style={{ marginTop: '1rem', fontSize: '0.9rem' }}>
          <div><strong>Quote time:</strong> {data.signal_ts ? formatTs(String(data.signal_ts)) : '—'}</div>
          <div><strong>Created:</strong> {data.created_at ? formatDateTime(String(data.created_at)) : '—'}</div>
          <div><strong>Execution mode:</strong> {executionMode ?? '—'}</div>
          {paperOrderId && (
            <div>
              <strong>Paper order:</strong>{' '}
              <Link to={`/orders/${paperOrderId}`} className="link-mono">
                {paperOrderId.slice(0, 16)}…
              </Link>
            </div>
          )}
          {lifecycle && (
            <>
              <div>
                <strong>Lifecycle status:</strong>{' '}
                <ManagedStatusBadge status={lifecycle.managed_status} />
              </div>
              {lifecycle.entry_order_id && (
                <div>
                  <strong>Entry order:</strong>{' '}
                  <Link to={`/orders/${lifecycle.entry_order_id}`} className="link-mono">
                    {lifecycle.entry_order_id.slice(0, 16)}…
                  </Link>
                </div>
              )}
              {lifecycle.exit_order_id && (
                <div>
                  <strong>Exit order:</strong>{' '}
                  <Link to={`/orders/${lifecycle.exit_order_id}`} className="link-mono">
                    {lifecycle.exit_order_id.slice(0, 16)}…
                  </Link>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {lifecycle && (
        <section className="dashboard-section">
          <SectionHeader title="Exit Plan & Protection" subtitle="Lifecycle-managed exit strategy" />
          <div className="grid-cards grid-cards--4">
            <div>
              <div className="kpi-card__title">Stop Price</div>
              <div className="kpi-card__value">{lifecycle.stop_price != null ? `$${lifecycle.stop_price.toFixed(2)}` : '—'}</div>
            </div>
            <div>
              <div className="kpi-card__title">Target Price</div>
              <div className="kpi-card__value">{lifecycle.target_price != null ? `$${lifecycle.target_price.toFixed(2)}` : '—'}</div>
            </div>
            <div>
              <div className="kpi-card__title">Force-Flat Time</div>
              <div className="kpi-card__value">{lifecycle.force_flat_time ?? '—'}</div>
            </div>
            <div>
              <div className="kpi-card__title">Protection</div>
              <div className="kpi-card__value">
                <ProtectionModeBadge mode={lifecycle.protection_mode} active={lifecycle.protection_active} />
              </div>
            </div>
          </div>
          {lifecycle.static_fallback_at_entry && (
            <div className="info-note" style={{ marginTop: '1rem', borderLeft: '3px solid var(--color-warning)', backgroundColor: 'var(--color-warning-bg, #2d2b1b)' }}>
              <strong>⚠ Static Fallback:</strong> This position was opened while using static fallback symbols.
            </div>
          )}
          <div style={{ marginTop: '1rem' }}>
            <Link to="/portfolio" className="link-mono">View position in Portfolio →</Link>
          </div>
        </section>
      )}

      {reasonCodes.length > 0 && (
        <section className="dashboard-section">
          <SectionHeader title="Decision Reasons" subtitle="Deterministic strategy reason codes" />
          <div className="badge-row">
            {reasonCodes.map((code) => (
              <StateBadge key={code} label={code} variant="default" />
            ))}
          </div>
        </section>
      )}

      {(intelligenceSnapshot || aiRefereeAssessment) && (
        <section className="dashboard-section">
          <SectionHeader title="Intelligence Participation" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {intelligenceSnapshot && (
              <div>
                <h3 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>🧠 Scrappy Intelligence</h3>
                <div style={{ fontSize: '0.9rem' }}>
                  <div><strong>Catalyst:</strong> {String(intelligenceSnapshot.catalyst_strength ?? '—')} {String(intelligenceSnapshot.catalyst_direction ?? '')}</div>
                  <div><strong>Sentiment:</strong> {String(intelligenceSnapshot.sentiment_label ?? '—')}</div>
                  <div><strong>Evidence:</strong> {Number(intelligenceSnapshot.evidence_count ?? 0)} sources, {Number(intelligenceSnapshot.headline_count ?? 0)} headlines</div>
                  {intelligenceSnapshot.stale_flag ? <div className="flag-badge flag-badge--warn">Stale</div> : null}
                  {intelligenceSnapshot.conflict_flag ? <div className="flag-badge flag-badge--warn">Conflict</div> : null}
                </div>
              </div>
            )}
            {aiRefereeAssessment && (
              <div>
                <h3 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>🤖 AI Referee Assessment</h3>
                <div style={{ fontSize: '0.9rem' }}>
                  <div><strong>Decision:</strong> {String(aiRefereeAssessment.decision_class ?? '—')}</div>
                  <div><strong>Score:</strong> {aiRefereeAssessment.setup_quality_score != null ? Number(aiRefereeAssessment.setup_quality_score).toFixed(2) : '—'}</div>
                  {aiRefereeAssessment.plain_english_rationale ? (
                    <div style={{ marginTop: '0.5rem', padding: '0.5rem', backgroundColor: 'var(--color-bg-secondary)', borderRadius: '4px' }}>
                      {String(aiRefereeAssessment.plain_english_rationale)}
                    </div>
                  ) : null}
                </div>
              </div>
            )}
            {!intelligenceSnapshot && !aiRefereeAssessment && (
              <div className="muted-text">No intelligence data available for this signal.</div>
            )}
          </div>
        </section>
      )}

      {scrappyReasonCodes.length > 0 && (
        <section className="dashboard-section">
          <SectionHeader title="Scrappy Reason Codes" subtitle="Additional reasons from intelligence layer" />
          <div className="badge-row">
            {scrappyReasonCodes.map((code) => (
              <StateBadge key={code} label={code} variant="default" />
            ))}
          </div>
        </section>
      )}

      <section className="dashboard-section">
        <SectionHeader title="Raw Data" subtitle="Full signal JSON for debugging" />
        <div className="info-note">
          <pre style={{ fontSize: '0.85rem', overflow: 'auto', maxHeight: 400 }}>
            {JSON.stringify(data, null, 2) as string}
          </pre>
        </div>
      </section>
    </div>
  );
}
