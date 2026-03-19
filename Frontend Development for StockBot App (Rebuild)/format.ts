/**
 * Shared formatting utilities for the StockBot operator console.
 */

/**
 * Format an ISO timestamp string into a human-readable relative time
 * (e.g. "2 min ago") or absolute time if older than 24 hours.
 */
export function formatTs(ts: string | null | undefined): string {
  if (!ts) return '—';
  const date = new Date(ts);
  if (isNaN(date.getTime())) return ts;
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 0) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/**
 * Format a number as a dollar P&L value with sign and 2 decimal places.
 */
export function formatPnl(value: number | null | undefined): string {
  if (value == null) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}$${value.toFixed(2)}`;
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
