/**
 * Utility functions and formatting helpers for incident evidence data.
 */

export function formatTimestamp(ts: number | null | undefined): string {
  if (!ts || isNaN(ts)) return 'N/A';
  const ms = ts < 1e11 ? ts * 1000 : ts;
  const date = new Date(ms);
  if (isNaN(date.getTime())) return 'Invalid date';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatDuration(startTs: number, endTs?: number | null): string {
  if (!startTs) return 'N/A';
  const end = endTs || Date.now() / 1000;
  const durationSec = Math.max(0, Math.round(end - startTs));
  const mins = Math.floor(durationSec / 60);
  const secs = durationSec % 60;
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

export const SEVERITY_BADGES: Record<string, string> = {
  critical: 'bg-rose-100 text-rose-800 border-rose-300',
  high: 'bg-amber-100 text-amber-800 border-amber-300',
  medium: 'bg-blue-100 text-blue-800 border-blue-300',
  low: 'bg-slate-100 text-slate-800 border-slate-300',
  unclassified: 'bg-slate-100 text-slate-700 border-slate-300',
};

export const STATUS_BADGES: Record<string, string> = {
  open: 'bg-rose-50 text-rose-700 border-rose-200',
  ongoing: 'bg-red-50 text-red-700 border-red-200',
  resolved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  closed: 'bg-slate-100 text-slate-700 border-slate-200',
  interrupted: 'bg-amber-50 text-amber-700 border-amber-200',
};

