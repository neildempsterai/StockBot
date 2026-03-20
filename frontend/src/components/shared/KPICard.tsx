type Variant = 'default' | 'shadow';

export function KPICard({
  title,
  value,
  subtitle,
  variant = 'default',
  valueClass = '',
}: {
  title: string;
  value: React.ReactNode;
  subtitle?: string;
  variant?: Variant;
  valueClass?: string;
}) {
  return (
    <div className={`kpi-card ${variant === 'shadow' ? 'kpi-card--shadow' : ''}`}>
      <div className="kpi-card__title">{title}</div>
      <div className={`kpi-card__value ${valueClass}`}>{value}</div>
      {subtitle && <div className="kpi-card__subtitle muted-text">{subtitle}</div>}
    </div>
  );
}
