export function RefreshBadge({
  dataUpdatedAt,
  isFetching,
  intervalSec,
}: {
  dataUpdatedAt?: number;
  isFetching?: boolean;
  intervalSec?: number;
}) {
  const time = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—';
  return (
    <span className="refresh-badge muted-text">
      {isFetching ? 'Refreshing…' : `Updated ${time}`}
      {intervalSec != null && ` · every ${intervalSec}s`}
    </span>
  );
}
