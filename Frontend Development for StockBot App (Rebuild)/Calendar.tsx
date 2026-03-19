import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet, ApiError } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';

interface CalendarDay {
  date: string;
  open?: string;
  close?: string;
  session_open?: string;
  session_close?: string;
}

interface CalendarResponse {
  calendar?: CalendarDay[];
  [key: string]: unknown;
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function nDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function nDaysAhead(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function isEarlyClose(day: CalendarDay): boolean {
  if (!day.close) return false;
  // Early close if market closes before 16:00
  const [h] = day.close.split(':').map(Number);
  return h < 16;
}

export function Calendar() {
  const today = todayStr();
  const [start, setStart] = useState(nDaysAgo(14));
  const [end, setEnd] = useState(nDaysAhead(30));

  const { data, isLoading, error } = useQuery<CalendarResponse, ApiError>({
    queryKey: ['calendar', start, end],
    queryFn: () =>
      apiGet<CalendarResponse>(ENDPOINTS.calendar, { start, end }),
    staleTime: 60_000 * 60, // calendar doesn't change often
  });

  const isUnconfigured = (error as ApiError)?.status === 503;
  const errorDetail = (error as ApiError)?.detail;

  // Normalise: API may return array directly or wrapped
  const raw = data?.calendar ?? (Array.isArray(data) ? (data as CalendarDay[]) : []);
  const days: CalendarDay[] = raw;

  return (
    <div className="page-content">
      <SectionHeader
        title="Trading Calendar"
        subtitle="NYSE/NASDAQ market open days from Alpaca"
      />

      <div className="filter-row" style={{ alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
        <label className="filter-label">From</label>
        <input
          type="date"
          className="date-input"
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
        <label className="filter-label">To</label>
        <input
          type="date"
          className="date-input"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
      </div>

      {isLoading && <LoadingSkeleton rows={10} />}

      {isUnconfigured ? (
        <BackendNotConnected
          message="Alpaca not configured"
          detail={errorDetail ?? 'Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY to enable.'}
        />
      ) : error && !isUnconfigured ? (
        <BackendNotConnected message="Could not load calendar" detail={errorDetail} />
      ) : !isLoading && (
        <>
          {days.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon">📅</div>
              <div className="empty-state__msg">No trading days found for this range</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Day</th>
                    <th>Open</th>
                    <th>Close</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {days.map((day) => {
                    const isToday = day.date === today;
                    const earlyClose = isEarlyClose(day);
                    return (
                      <tr key={day.date} className={isToday ? 'row--highlight' : ''}>
                        <td className="cell--symbol">{day.date}</td>
                        <td>{new Date(day.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short' })}</td>
                        <td>{day.open ?? day.session_open ?? '—'}</td>
                        <td>{day.close ?? day.session_close ?? '—'}</td>
                        <td>
                          {isToday && <span className="badge badge--green">Today</span>}
                          {earlyClose && <span className="badge badge--yellow" style={{ marginLeft: '0.25rem' }}>Early close</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <div className="info-note" style={{ marginTop: '0.75rem' }}>
            {days.length} trading day{days.length !== 1 ? 's' : ''} · {start} → {end}
          </div>
        </>
      )}
    </div>
  );
}
