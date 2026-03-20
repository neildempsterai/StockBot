export function EmptyState({ message, icon }: { message: string; icon?: string }) {
  return (
    <div className="empty-state">
      {icon && <span className="empty-state__icon">{icon}</span>}
      <p className="muted-text">{message}</p>
    </div>
  );
}
