import type { AxiosError } from 'axios';

export function formatFastApiDetail(detail: unknown): string {
  if (detail === undefined || detail === null) return '';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(x => JSON.stringify(x)).join('; ');
  return JSON.stringify(detail);
}

export function messageFromAxios(e: unknown): string {
  const ax = e as AxiosError<{ detail?: unknown }>;
  return formatFastApiDetail(ax.response?.data?.detail) || ax.message || String(e);
}
