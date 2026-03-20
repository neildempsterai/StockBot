import { StateBadge } from './StateBadge';

type Source = 'strategy_paper' | 'operator_test' | 'legacy_unknown';

interface SourceBadgeProps {
  source?: Source | string | null;
}

export function SourceBadge({ source }: SourceBadgeProps) {
  if (!source) return <span className="muted-text">—</span>;
  const s = String(source).toLowerCase();
  let variant: 'success' | 'warning' | 'error' | 'default' = 'default';
  let label = s;
  if (s === 'strategy_paper') {
    variant = 'success';
    label = 'Strategy';
  } else if (s === 'operator_test') {
    variant = 'default';
    label = 'Operator Test';
  } else if (s === 'legacy_unknown') {
    variant = 'warning';
    label = 'Legacy';
  }
  return <StateBadge label={label} variant={variant} />;
}
