export function BackendNotConnected({
  message,
  detail,
}: {
  message: string;
  detail?: string;
}) {
  return (
    <div className="info-note" style={{ borderColor: 'var(--color-warning)' }}>
      <strong>{message}</strong>
      {detail && <p className="muted-text" style={{ marginTop: '0.5rem', marginBottom: 0 }}>{detail}</p>}
    </div>
  );
}
