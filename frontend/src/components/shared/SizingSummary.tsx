interface SizingSummaryProps {
  sizing?: {
    equity?: number;
    buying_power?: number;
    qty_approved?: number;
    notional_approved?: number;
    risk_per_trade_pct?: number;
    rejection_reason?: string;
  } | null;
  compact?: boolean;
}

export function SizingSummary({ sizing, compact }: SizingSummaryProps) {
  if (!sizing) return <span className="muted-text">—</span>;
  if (sizing.rejection_reason) {
    return <span className="muted-text" style={{ color: 'var(--color-error)' }}>Rejected: {sizing.rejection_reason}</span>;
  }
  if (compact) {
    return (
      <span className="muted-text" style={{ fontSize: '0.85rem' }}>
        {sizing.qty_approved != null ? `${sizing.qty_approved} shares` : '—'}
        {sizing.notional_approved != null && ` ($${Number(sizing.notional_approved).toFixed(0)})`}
      </span>
    );
  }
  return (
    <div style={{ fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
      {sizing.qty_approved != null && <div>Qty: {sizing.qty_approved}</div>}
      {sizing.notional_approved != null && <div>Notional: ${Number(sizing.notional_approved).toFixed(2)}</div>}
      {sizing.equity != null && <div>Equity: ${Number(sizing.equity).toFixed(2)}</div>}
      {sizing.risk_per_trade_pct != null && <div>Risk: {Number(sizing.risk_per_trade_pct).toFixed(2)}%</div>}
    </div>
  );
}
