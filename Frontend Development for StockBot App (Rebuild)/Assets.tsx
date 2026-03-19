import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiGet, ApiError } from '../api/client';
import { ENDPOINTS } from '../api/endpoints';
import { SectionHeader } from '../components/shared/SectionHeader';
import { LoadingSkeleton } from '../components/shared/LoadingSkeleton';
import { BackendNotConnected } from '../components/shared/BackendNotConnected';

interface Asset {
  id: string;
  symbol: string;
  name?: string;
  exchange?: string;
  asset_class?: string;
  status?: string;
  tradable?: boolean;
  shortable?: boolean;
  fractionable?: boolean;
  [key: string]: unknown;
}

interface AssetsResponse {
  assets?: Asset[];
  [key: string]: unknown;
}

export function Assets() {
  const [search, setSearch] = useState('');

  const { data, isLoading, error } = useQuery<AssetsResponse, ApiError>({
    queryKey: ['assets'],
    queryFn: () =>
      apiGet<AssetsResponse>(ENDPOINTS.assets, { status: 'active', asset_class: 'us_equity' }),
    staleTime: 60_000 * 10,
  });

  const isUnconfigured = (error as ApiError)?.status === 503;
  const errorDetail = (error as ApiError)?.detail;

  const raw: Asset[] = data?.assets ?? (Array.isArray(data) ? (data as Asset[]) : []);

  const filtered = useMemo(() => {
    if (!search.trim()) return raw;
    const q = search.trim().toUpperCase();
    return raw.filter(
      (a) =>
        a.symbol.toUpperCase().includes(q) ||
        (a.name ?? '').toUpperCase().includes(q)
    );
  }, [raw, search]);

  return (
    <div className="page-content">
      <SectionHeader
        title="Assets"
        subtitle="Active US equity assets available on Alpaca"
      />

      {isLoading && <LoadingSkeleton rows={12} />}

      {isUnconfigured ? (
        <BackendNotConnected
          message="Alpaca not configured"
          detail={errorDetail ?? 'Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY to enable.'}
        />
      ) : error && !isUnconfigured ? (
        <BackendNotConnected message="Could not load assets" detail={errorDetail} />
      ) : !isLoading && (
        <>
          <div className="filter-row" style={{ marginBottom: '1rem' }}>
            <input
              type="text"
              className="search-input"
              placeholder="Search symbol or name…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <span className="filter-count">
              {filtered.length.toLocaleString()} / {raw.length.toLocaleString()} assets
            </span>
          </div>

          {filtered.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon">🔍</div>
              <div className="empty-state__msg">No assets match "{search}"</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Name</th>
                    <th>Exchange</th>
                    <th>Tradable</th>
                    <th>Shortable</th>
                    <th>Fractionable</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, 500).map((a) => (
                    <tr key={a.id}>
                      <td className="cell--symbol">{a.symbol}</td>
                      <td style={{ maxWidth: '260px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {a.name ?? '—'}
                      </td>
                      <td>{a.exchange ?? '—'}</td>
                      <td>
                        {a.tradable === true ? (
                          <span className="badge badge--green">Yes</span>
                        ) : a.tradable === false ? (
                          <span className="badge badge--red">No</span>
                        ) : '—'}
                      </td>
                      <td>
                        {a.shortable === true ? (
                          <span className="badge badge--green">Yes</span>
                        ) : a.shortable === false ? (
                          <span className="badge badge--dim">No</span>
                        ) : '—'}
                      </td>
                      <td>
                        {a.fractionable === true ? (
                          <span className="badge badge--green">Yes</span>
                        ) : a.fractionable === false ? (
                          <span className="badge badge--dim">No</span>
                        ) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filtered.length > 500 && (
                <div className="info-note" style={{ marginTop: '0.5rem' }}>
                  Showing first 500 results. Refine your search to narrow down.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
