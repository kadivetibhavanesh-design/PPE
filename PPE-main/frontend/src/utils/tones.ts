import type { Tone } from '@/types/overview';

/** Shared Tailwind class sets per semantic tone (green = compliant, amber = review, red = violation). */
export const TONE_CLASSES: Record<Tone, { badge: string; icon: string; dot: string; hex: string }> = {
  blue: { badge: 'bg-blue-50 text-blue-700 border-blue-200', icon: 'bg-blue-50 text-blue-700 ring-blue-100', dot: 'bg-blue-500', hex: '#2563eb' },
  green: { badge: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: 'bg-emerald-50 text-emerald-700 ring-emerald-100', dot: 'bg-emerald-500', hex: '#10b981' },
  amber: { badge: 'bg-amber-50 text-amber-800 border-amber-200', icon: 'bg-amber-50 text-amber-700 ring-amber-100', dot: 'bg-amber-500', hex: '#f59e0b' },
  red: { badge: 'bg-red-50 text-red-700 border-red-200', icon: 'bg-red-50 text-red-700 ring-red-100', dot: 'bg-red-500', hex: '#ef4444' },
  slate: { badge: 'bg-slate-100 text-slate-600 border-slate-200', icon: 'bg-slate-100 text-slate-600 ring-slate-200', dot: 'bg-slate-400', hex: '#64748b' },
};

