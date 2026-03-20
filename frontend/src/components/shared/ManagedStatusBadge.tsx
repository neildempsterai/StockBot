import { StateBadge } from './StateBadge';

type ManagedStatus = 'managed' | 'unmanaged' | 'orphaned' | 'exited' | 'pending' | 'blocked';

interface ManagedStatusBadgeProps {
  status?: ManagedStatus | string | null;
}

export function ManagedStatusBadge({ status }: ManagedStatusBadgeProps) {
  if (!status) return <span className="muted-text">—</span>;
  const s = String(status).toLowerCase();
  let variant: 'success' | 'warning' | 'error' | 'default' = 'default';
  let label = s;
  if (s === 'managed') {
    variant = 'success';
    label = 'Managed';
  } else if (s === 'orphaned') {
    variant = 'error';
    label = 'Orphaned';
  } else if (s === 'unmanaged') {
    variant = 'warning';
    label = 'Unmanaged';
  } else if (s === 'exited') {
    variant = 'default';
    label = 'Exited';
  } else if (s === 'pending') {
    variant = 'default';
    label = 'Pending';
  } else if (s === 'blocked') {
    variant = 'error';
    label = 'Blocked';
  }
  return <StateBadge label={label} variant={variant} />;
}
