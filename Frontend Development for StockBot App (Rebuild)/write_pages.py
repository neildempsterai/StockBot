import os

base = '/home/ubuntu/StockBot/frontend/src/pages'

files = {}

files['AiReferee.tsx'] = """import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { AiRefereeRecentResponse } from '../types/api';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { RefreshBadge } from '../components/shared/RefreshBadge';
import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';
import { formatTs } from '../utils/format';

const DECISION_VARIANTS: Record<string, string> = {
  approve: 'success',
  reject: 'error',
  advisory: 'warning',
  skip: 'neutral',
};

export function AiReferee() {
  const { data, isLoading, isError, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['aiRefereeRecent'],
    queryFn: () => apiGet<AiRefereeRecentResponse>(`${ENDPOINTS.aiRefereeRecent}?limit=30`),
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <div>
        <h1 className="page-title">AI Referee</h1>
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div>
        <h1 className="page-title">AI Referee</h1>
        <BackendNotConnected message="Could not load AI referee assessments from API" />
      </div>
    );
  }

  const { assessments, count } = data;

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">AI Referee</h1>
        <RefreshBadge dataUpdatedAt={dataUpdatedAt} isFetching={isFetching} intervalSec={30} />
      </div>
      <SectionHeader
        title={`${count} assessment${count !== 1 ? 's' : ''}`}
        subtitle="Most recent 30 AI referee decisions"
      />
      {count === 0 || !assessments?.length ? (
        <EmptyState message="No assessments yet." icon="\\u{1F916}" />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Score</th>
                <th>Decision</th>
                <th>Catalyst</th>
                <th>Evidence</th>
                <th>Stale</th>
                <th>Contradiction</th>
                <th>Model</th>
                <th>Time</th>
                <th>Rationale</th>
              </tr>
            </thead>
            <tbody>
              {assessments.map((a) => {
                const variant = DECISION_VARIANTS[a.decision_class?.toLowerCase() ?? ''] ?? 'neutral';
                const scoreLevel = a.setup_quality_score >= 7 ? 'high' : a.setup_quality_score >= 4 ? 'mid' : 'low';
                return (
                  <tr key={a.assessment_id}>
                    <td className="cell--symbol">{a.symbol}</td>
                    <td>
                      <span className={`score-badge score-badge--${scoreLevel}`}>
                        {a.setup_quality_score}
                      </span>
                    </td>
                    <td>
                      <span className={`state-badge state-badge--${variant}`}>
                        {a.decision_class ?? '\\u2014'}
                      </span>
                    </td>
                    <td>{a.catalyst_strength ?? '\\u2014'}</td>
                    <td>{a.evidence_sufficiency ?? '\\u2014'}</td>
                    <td>
                      {a.stale_flag != null ? (
                        <span className={`flag-badge flag-badge--${a.stale_flag ? 'warn' : 'ok'}`}>
                          {a.stale_flag ? 'stale' : 'fresh'}
                        </span>
                      ) : '\\u2014'}
                    </td>
                    <td>
                      {a.contradiction_flag != null ? (
                        <span className={`flag-badge flag-badge--${a.contradiction_flag ? 'warn' : 'ok'}`}>
                          {a.contradiction_flag ? 'yes' : 'no'}
                        </span>
                      ) : '\\u2014'}
                    </td>
                    <td className="cell--muted cell--small">{a.model_name ?? '\\u2014'}</td>
                    <td className="cell--ts" title={a.assessment_ts ?? ''}>{formatTs(a.assessment_ts)}</td>
                    <td className="cell--rationale" title={a.plain_english_rationale ?? ''}>
                      {(a.plain_english_rationale ?? '').slice(0, 100)}
                      {(a.plain_english_rationale ?? '').length > 100 ? '\\u2026' : ''}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
"""

files['Portfolio.tsx'] = """import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { ShadowTradesResponse, MetricsSummaryResponse } from '../types/api';
import { KPICard } from '../components/shared/KPICard';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { SectionHeader } from '../components/shared/SectionHeader';
import { formatPnl, pnlClass } from '../utils/format';

export function Portfolio() {
  const { data: shadowTrades, isLoading: tradesLoading, error: tradesError } = useQuery({
    queryKey: ['shadowTrades'],
    queryFn: () => apiGet<ShadowTradesResponse>(`${ENDPOINTS.shadowTrades}?limit=50`),
    refetchInterval: 30_000,
  });
  const { data: metrics, error: metricsError } = useQuery({
    queryKey: ['metricsSummary'],
    queryFn: () => apiGet<MetricsSummaryResponse>(ENDPOINTS.metricsSummary),
    refetchInterval: 30_000,
  });

  const err = tradesError || metricsError;
  const apiErrorDetail = err && typeof err === 'object' && 'detail' in err
    ? String((err as { detail?: string }).detail)
    : undefined;

  if (tradesLoading) {
    return (
      <div>
        <h1 className="page-title">Portfolio</h1>
        <LoadingSkeleton lines={4} />
      </div>
    );
  }

  const pnl = metrics?.total_net_pnl_shadow ?? null;

  return (
    <div className="page-stack">
      <h1 className="page-title">Portfolio</h1>
      <section>
        <SectionHeader title="Paper Account" subtitle="Broker-connected paper trading" />
        <BackendNotConnected message="Paper account (broker) not yet connected to backend. No paper positions or cash from API." />
      </section>
      <section>
        <SectionHeader title="Shadow Book" subtitle="Internal fill ledger \\u2014 shadow trades only" />
        {!shadowTrades && !metrics ? (
          <BackendNotConnected message="Could not load shadow data from API" detail={apiErrorDetail} />
        ) : (
          <div className="grid-cards">
            <KPICard
              title="Shadow trades"
              value={metrics?.shadow_trades_total ?? shadowTrades?.count ?? 0}
              variant="shadow"
            />
            <KPICard
              title="Net P&L (shadow)"
              value={pnl != null ? formatPnl(pnl) : '\\u2014'}
              variant="shadow"
              valueClass={pnlClass(pnl)}
            />
          </div>
        )}
      </section>
    </div>
  );
}
"""

files['SystemHealth.tsx'] = """import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { HealthResponse } from '../types/api';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { StateBadge } from '../components/shared/StateBadge';
import { RefreshBadge } from '../components/shared/RefreshBadge';
import { SectionHeader } from '../components/shared/SectionHeader';

export function SystemHealth() {
  const { data, isLoading, isError, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>(ENDPOINTS.health),
    refetchInterval: 10_000,
  });

  if (isLoading) {
    return (
      <div>
        <h1 className="page-title">System Health</h1>
        <LoadingSkeleton lines={3} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div>
        <h1 className="page-title">System Health</h1>
        <BackendNotConnected message="API unreachable. Service uptime and latency are not available from backend." />
      </div>
    );
  }

  const apiOk = data.status === 'ok';

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">System Health</h1>
        <RefreshBadge dataUpdatedAt={dataUpdatedAt} isFetching={isFetching} intervalSec={10} />
      </div>
      <SectionHeader title="API Status" />
      <div className="grid-cards">
        <div className={`kpi-card kpi-card--status ${apiOk ? 'kpi-card--ok' : 'kpi-card--err'}`}>
          <div className="kpi-card__title">API</div>
          <div className="kpi-card__value">
            <StateBadge label={data.status} variant={apiOk ? 'success' : 'error'} />
          </div>
        </div>
      </div>
      <SectionHeader title="Services" subtitle="Detailed health not yet connected" />
      <div className="grid-cards">
        {['Worker', 'Redis', 'Postgres', 'Alpaca Gateway'].map((svc) => (
          <div key={svc} className="kpi-card">
            <div className="kpi-card__title">{svc}</div>
            <div className="kpi-card__value">
              <StateBadge label="\\u2014" variant="neutral" />
            </div>
            <div className="kpi-card__subtitle">Not yet exposed by API</div>
          </div>
        ))}
      </div>
      <div className="info-note">
        Backend exposes GET /health only. Detailed health metrics (uptime, latency, per-service) are not yet connected.
      </div>
    </div>
  );
}
"""

files['Settings.tsx'] = """import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { StrategiesResponse } from '../types/api';
import { SectionHeader } from '../components/shared/SectionHeader';

export function Settings() {
  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => apiGet<StrategiesResponse>(ENDPOINTS.strategies),
  });

  const strategy = strategies?.strategies?.[0];

  return (
    <div className="page-stack">
      <h1 className="page-title">Settings</h1>
      <SectionHeader title="Active Strategy" subtitle="Read-only \\u2014 no settings are currently exposed by the backend" />
      <div className="settings-table">
        {([
          ['Strategy ID', strategy?.strategy_id],
          ['Version', strategy?.strategy_version],
          ['Mode', strategy?.mode],
          ['Entry window (ET)', strategy?.entry_window_et],
          ['Force flat (ET)', strategy?.force_flat_et],
        ] as [string, string | undefined][]).map(([key, val]) => (
          <div key={key} className="settings-row">
            <span className="settings-row__key">{key}</span>
            <span className="settings-row__value">{val ?? '\\u2014'}</span>
          </div>
        ))}
      </div>
      <SectionHeader title="Environment" subtitle="Backend does not yet expose GET /v1/config" />
      <div className="settings-table">
        {['SCRAPPY_MODE', 'AI_REFEREE_MODE', 'AI_REFEREE_ENABLED', 'STOCKBOT_UNIVERSE'].map((key) => (
          <div key={key} className="settings-row">
            <span className="settings-row__key">{key}</span>
            <span className="settings-row__value cell--muted">\\u2014 (not yet exposed)</span>
          </div>
        ))}
      </div>
      <div className="info-note">
        No settings are currently writable from the frontend. All configuration is managed via environment variables on the backend.
      </div>
    </div>
  );
}
"""

files['History.tsx'] = """import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SectionHeader } from '../components/shared/SectionHeader';

export function History() {
  return (
    <div className="page-stack">
      <h1 className="page-title">History</h1>
      <SectionHeader title="Release History" subtitle="Deployment and release history" />
      <BackendNotConnected message="History / release / deployment history backend not yet connected." />
    </div>
  );
}
"""

files['StrategyLab.tsx'] = """import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { SectionHeader } from '../components/shared/SectionHeader';

export function StrategyLab() {
  return (
    <div className="page-stack">
      <h1 className="page-title">Strategy Lab</h1>
      <SectionHeader title="Backtest Runner" subtitle="Historical test execution" />
      <BackendNotConnected message="Historical test execution (backtest) is not yet wired to the backend. Controls are disabled until a backtest endpoint is available." />
    </div>
  );
}
"""

for fname, content in files.items():
    path = os.path.join(base, fname)
    with open(path, 'w') as f:
        f.write(content)
    print(f'Written: {fname}')

print('All done')
