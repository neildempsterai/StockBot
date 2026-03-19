import { formatTs } from '../../utils/format';

interface RefreshBadgeProps {
  dataUpdatedAt?: number;
  isFetching?: boolean;
  intervalSec?: number;
}

export function RefreshBadge({ dataUpdatedAt, isFetching, intervalSec }: RefreshBadgeProps) {
  const lastUpdated = dataUpdatedAt
    ? formatTs(new Date(dataUpdatedAt).toISOString())
    : null;

  return (
    <div className="refresh-badge">
      <span className={`refresh-badge__dot${isFetching ? ' refresh-badge__dot--fetching' : ''}`} />
      <span className="refresh-badge__text">
        {isFetching
          ? 'Refreshing…'
          : lastUpdated
          ? `Updated ${lastUpdated}`
          : 'Waiting for data'}
      </span>
      {intervalSec && !isFetching && (
        <span className="refresh-badge__interval">· every {intervalSec}s</span>
      )}
    </div>
  );
}
