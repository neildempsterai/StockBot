type Variant = 'success' | 'error' | 'warning' | 'neutral' | 'default';

export function StateBadge({
  label,
  variant = 'default',
}: {
  label: string;
  variant?: Variant;
}) {
  return (
    <span className={`state-badge state-badge--${variant}`}>
      {label}
    </span>
  );
}
