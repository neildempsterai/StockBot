/** UK locale for all date/time display (DD/MM/YYYY, 24h). */
const UK_LOCALE = 'en-GB';

/**
 * Shared formatting utilities for the StockBot operator console.
 */

/**
 * Format a Date or ISO string as UK date+time (DD/MM/YYYY, HH:MM:SS).
 */
export function formatDateTime(value: Date | string | null | undefined): string {
  if (value == null) return '—';
  const date = typeof value === 'string' ? new Date(value) : value;
  if (isNaN(date.getTime())) return '—';
  return date.toLocaleString(UK_LOCALE, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/**
 * Format a Date or ISO string as UK time only (24h).
 */
export function formatTime(value: Date | string | number | null | undefined): string {
  if (value == null) return '—';
  const date = typeof value === 'number' ? new Date(value * 1000) : new Date(value);
  if (isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString(UK_LOCALE, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

/**
 * Format an ISO timestamp string into a human-readable relative time
 * (e.g. "2 min ago") or absolute time if older than 24 hours. Uses UK locale.
 */
export function formatTs(ts: string | null | undefined): string {
  if (!ts) return '—';
  const date = new Date(ts);
  if (isNaN(date.getTime())) return ts;
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 0) return date.toLocaleTimeString(UK_LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false });
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return date.toLocaleDateString(UK_LOCALE, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
}

/**
 * Format a number as a dollar P&L value with sign, thousand separators, and 2 decimal places.
 */
export function formatPnl(value: number | null | undefined): string {
  if (value == null) return '—';
  // Use Intl.NumberFormat for proper thousand separators and currency formatting
  // signDisplay: 'always' ensures + for positive, - for negative, but it doesn't work with currency style
  // So we'll use 'exceptZero' and manually add + for positive values
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(value));
  // Add sign prefix for P&L display
  if (value > 0) {
    return `+${formatted}`;
  } else if (value < 0) {
    return `-${formatted}`;
  }
  return formatted; // Zero has no sign
}

/**
 * Return a CSS class name based on P&L sign.
 */
export function pnlClass(value: number | null | undefined): string {
  if (value == null) return '';
  if (value > 0) return 'pnl--positive';
  if (value < 0) return 'pnl--negative';
  return 'pnl--zero';
}

/**
 * Format a number as a price with 2 decimal places.
 */
export function formatPrice(value: number | null | undefined): string {
  if (value == null) return '—';
  return `$${value.toFixed(2)}`;
}

/**
 * Truncate a UUID to 8 chars with ellipsis.
 */
export function shortUuid(uuid: string): string {
  return `${uuid.slice(0, 8)}…`;
}

/** Known session values from clock API; display with consistent title case. */
const SESSION_LABELS: Record<string, string> = {
  premarket: 'Premarket',
  regular: 'Regular',
  after_hours: 'After hours',
  closed: 'Closed',
  overnight: 'Overnight',
};

/**
 * Format market session for display (e.g. premarket -> Premarket).
 */
export function formatSession(session: string | null | undefined): string {
  if (session == null || session === '') return '—';
  const lower = session.toLowerCase().replace(/-/g, '_');
  return SESSION_LABELS[lower] ?? session.charAt(0).toUpperCase() + session.slice(1).toLowerCase();
}
