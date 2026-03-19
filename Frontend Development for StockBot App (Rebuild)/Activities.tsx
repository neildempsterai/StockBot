import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet, ApiError } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { AccountActivitiesResponse, AccountActivity } from '../types/api';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { formatTs } from '../utils/format';

function sideBadgeClass(side?: string): string {
  if (!side) return '';
  return side.toLowerCase() === 'buy' ? 'signal-side signal-side--buy' : 'signal-side signal-side--sell';
}

function ActivityRow({ act }: { act: AccountActivity }) {
  const ts = act.transaction_time
    ? formatTs(String(act.transaction_time))
    : act.date
    ? String(act.date)
    : '—';
  const symbol = (act.symbol as string | undefined) ?? '—';
  const qty = (act.qty as string | undefined) ?? '—';
  const side = act.side as string | undefined;
  const price = act.price != null ? `$${parseFloat(String(act.price)).toFixed(2)}` : '—';
  const netAmount = act.net_amount != null ? `$${parseFloat(String(act.net_amount)).toFixed(2)}` : '—';

  return (
    <tr>
      <td className="cell--ts">{ts}</td>
      <td>
        <span className="badge badge--dim">{act.activity_type ?? '—'}</span>
      </td>
      <td className="cell--symbol">{symbol}</td>
      <td>
        {side ? (
          <span className={sideBadgeClass(side)}>{side.toUpperCase()}</span>
        ) : '—'}
      </td>
      <td>{qty}</td>
      <td>{price}</td>
      <td>{netAmount}</td>
    </tr>
  );
}

export function Activities() {
  const [pageToken, setPageToken] = useState<string | undefined>(undefined);
  const [history, setHistory] = useState<string[]>([]);

  const { data, isLoading, error } = useQuery<AccountActivitiesResponse, ApiError>({
    queryKey: ['activities', pageToken],
    queryFn: () =>
      apiGet<AccountActivitiesResponse>(ENDPOINTS.accountActivities, {
        page_size: 50,
        ...(pageToken ? { page_token: pageToken } : {}),
      }),
    refetchInterval: 60_000,
  });

  const isUnconfigured = (error as ApiError)?.status === 503;
  const errorDetail = (error as ApiError)?.detail;
  const activities: AccountActivity[] = data?.activities ?? [];
  const nextToken = data?.next_page_token ?? null;

  function goNext() {
    if (!nextToken) return;
    setHistory((h) => [...h, pageToken ?? '']);
    setPageToken(nextToken);
  }

  function goPrev() {
    const prev = [...history];
    const tok = prev.pop();
    setHistory(prev);
    setPageToken(tok || undefined);
  }

  return (
    <div className="page-content">
      <SectionHeader
        title="Account Activities"
        subtitle="Trade confirmations, dividends, and other account events"
      />

      {isLoading && <LoadingSkeleton rows={8} />}

      {isUnconfigured ? (
        <BackendNotConnected
          message="Alpaca not configured"
          detail={errorDetail ?? 'Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY to enable.'}
        />
      ) : error && !isUnconfigured ? (
        <BackendNotConnected message="Could not load activities" detail={errorDetail} />
      ) : !isLoading && (
        <>
          {activities.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon">📄</div>
              <div className="empty-state__msg">No activities found</div>
            </div>
          ) : (
            <>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Type</th>
                      <th>Symbol</th>
                      <th>Side</th>
                      <th>Qty</th>
                      <th>Price</th>
                      <th>Net Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activities.map((a) => (
                      <ActivityRow key={a.id} act={a} />
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="pagination-row">
                <button
                  className="filter-btn"
                  onClick={goPrev}
                  disabled={history.length === 0}
                >
                  ← Previous
                </button>
                <span className="filter-count">{activities.length} activities</span>
                <button
                  className="filter-btn"
                  onClick={goNext}
                  disabled={!nextToken}
                >
                  Next →
                </button>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
