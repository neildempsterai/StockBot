/**
 * Typed API client for StockBot backend.
 * Base URL: /api when using Vite proxy to backend, or env VITE_API_BASE.
 */
const getEnv = (): { VITE_API_BASE?: string } => {
  try {
    return (import.meta as unknown as { env?: { VITE_API_BASE?: string } }).env ?? {};
  } catch {
    return {};
  }
};
const API_BASE = getEnv().VITE_API_BASE ? String(getEnv().VITE_API_BASE) : '/api';

export type ApiError = { status: number; detail?: string; message?: string };

async function handleResponse<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    let detail: string | undefined;
    try {
      const j = JSON.parse(text) as { detail?: string; message?: string };
      detail = j.detail ?? j.message ?? text;
    } catch {
      detail = text || res.statusText;
    }
    throw { status: res.status, detail } as ApiError;
  }
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export async function apiGet<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const pathOnly = path.split('?')[0];
  const pathQuery = path.includes('?') ? path.slice(path.indexOf('?')) : '';
  const url = new URL(path.startsWith('http') ? path : `${API_BASE}${pathOnly}${pathQuery}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString(), { headers: { Accept: 'application/json' } });
  return handleResponse<T>(res);
}

export async function apiPost<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const [pathOnly, pathQuery] = path.includes('?') ? path.split('?', 2) : [path, ''];
  const url = new URL(path.startsWith('http') ? path : `${API_BASE}${pathOnly}`, window.location.origin);
  if (pathQuery) {
    new URLSearchParams(pathQuery).forEach((v, k) => url.searchParams.set(k, v));
  }
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== '') url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
  });
  return handleResponse<T>(res);
}

/** POST with JSON body (e.g. paper test buy-open). */
export async function apiPostWithBody<T>(path: string, body: unknown): Promise<T> {
  const pathOnly = path.split('?')[0];
  const url = new URL(path.startsWith('http') ? path : `${API_BASE}${pathOnly}`, window.location.origin);
  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export { API_BASE };
