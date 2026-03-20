import { StateBadge } from './StateBadge';

type ProtectionMode = 'broker_native' | 'worker_mirrored' | 'unprotected' | 'unknown';

interface ProtectionModeBadgeProps {
  mode?: ProtectionMode | string | null;
  active?: boolean;
}

export function ProtectionModeBadge({ mode, active }: ProtectionModeBadgeProps) {
  if (!mode) return <span className="muted-text">—</span>;
  const m = String(mode).toLowerCase();
  let variant: 'success' | 'warning' | 'error' | 'default' = 'default';
  let label = m;
  if (m === 'broker_native') {
    variant = 'success';
    label = 'Broker Native';
  } else if (m === 'worker_mirrored') {
    variant = active ? 'success' : 'warning';
    label = 'Worker Mirrored';
  } else if (m === 'unprotected' || m === 'unknown') {
    variant = 'error';
    label = m === 'unprotected' ? 'Unprotected' : 'Unknown';
  }
  return <StateBadge label={label} variant={variant} />;
}
