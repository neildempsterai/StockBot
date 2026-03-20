import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import type { ConfigResponse } from '../types/api';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';

export function Settings() {
  const { data, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: () => apiGet<ConfigResponse>(ENDPOINTS.config),
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <div className="page-stack">
        <h1 className="page-title">Settings</h1>
        <LoadingSkeleton lines={6} />
      </div>
    );
  }

  const config = data ?? {};
  const entries = Object.entries(config).filter(([k]) => typeof config[k] !== 'object' || config[k] === null);

  return (
    <div className="page-stack">
      <h1 className="page-title">Settings</h1>
      <SectionHeader title="Runtime config" subtitle="Read-only from backend (env)" />
      <div className="table-wrap">
        <table className="data-table settings-table">
          <thead>
            <tr>
              <th>Key</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td className="cell--mono">{key}</td>
                <td>{String(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
