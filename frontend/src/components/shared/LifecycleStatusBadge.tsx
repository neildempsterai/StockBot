import { StateBadge } from './StateBadge';

type LifecycleStatus = 'planned' | 'entry_submitted' | 'entry_filled' | 'exit_pending' | 'exit_submitted' | 'exited' | 'orphaned' | 'blocked';

interface LifecycleStatusBadgeProps {
  status?: LifecycleStatus | string | null;
}

export function LifecycleStatusBadge({ status }: LifecycleStatusBadgeProps) {
  if (!status) return <span className="muted-text">—</span>;
  const s = String(status).toLowerCase();
  let variant: 'success' | 'warning' | 'error' | 'default' = 'default';
  let label = s.replace(/_/g, ' ');
  if (s === 'exited') {
    variant = 'success';
    label = 'Exited';
  } else if (s === 'entry_filled' || s === 'exit_submitted') {
    variant = 'success';
    label = s === 'entry_filled' ? 'Filled' : 'Exit Submitted';
  } else if (s === 'entry_submitted' || s === 'exit_pending') {
    variant = 'default';
    label = s === 'entry_submitted' ? 'Submitted' : 'Exit Pending';
  } else if (s === 'orphaned' || s === 'blocked') {
    variant = 'error';
    label = s === 'orphaned' ? 'Orphaned' : 'Blocked';
  } else if (s === 'planned') {
    variant = 'default';
    label = 'Planned';
  }
  return <StateBadge label={label} variant={variant} />;
}
