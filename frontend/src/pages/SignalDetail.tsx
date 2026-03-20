import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';
import { formatTs } from '../utils/format';

export function SignalDetail() {
  const { signalUuid } = useParams<{ signalUuid: string }>();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['signal', signalUuid],
    queryFn: () => apiGet<Record<string, unknown>>(ENDPOINTS.signalDetail(signalUuid!)),
    enabled: !!signalUuid,
  });

  if (!signalUuid) {
    return (
      <div className="page-stack">
        <p className="muted-text">No signal ID</p>
        <Link to="/signals">← Back to signals</Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Signal</h1>
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Signal</h1>
        <BackendNotConnected message="Could not load signal" />
        <Link to="/signals">← Back to signals</Link>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <div className="page-title-row">
        <h1 className="page-title">Signal {signalUuid.slice(0, 8)}…</h1>
        <Link to="/signals" className="link-mono">← Back to signals</Link>
      </div>
      <div className="info-note">
        <pre style={{ fontSize: '0.85rem', overflow: 'auto', maxHeight: 400 }}>
          {JSON.stringify(data, null, 2) as string}
        </pre>
      </div>
      <p className="muted-text">
        Quote time: {formatTs(data.quote_ts as string)} · Symbol: {String(data.symbol ?? '')} · Side: {String(data.side ?? '')}
      </p>
    </div>
  );
}
