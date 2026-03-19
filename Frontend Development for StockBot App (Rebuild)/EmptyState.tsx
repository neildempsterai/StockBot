interface EmptyStateProps {
  message: string;
  icon?: string;
}

export function EmptyState({ message, icon = '📭' }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="empty-state__icon">{icon}</span>
      <span className="empty-state__message">{message}</span>
    </div>
  );
}
