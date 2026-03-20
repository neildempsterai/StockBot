import { SectionHeader } from '../components/shared/SectionHeader';
import { EmptyState } from '../components/shared/EmptyState';

export function History() {
  return (
    <div className="page-stack">
      <h1 className="page-title">History</h1>
      <SectionHeader title="Trade history" subtitle="Historical view" />
      <EmptyState message="History view — use Shadow Trades and Portfolio for current data." icon="📋" />
    </div>
  );
}
