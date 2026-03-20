export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="section-header">
      <h2 className="section-header__title">{title}</h2>
      {subtitle && <span className="muted-text section-header__subtitle">{subtitle}</span>}
    </div>
  );
}
