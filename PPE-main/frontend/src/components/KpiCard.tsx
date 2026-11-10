import React from 'react';
import type { LucideIcon } from 'lucide-react';
import type { Tone } from '@/types/overview';
import { TONE_CLASSES } from '@/utils/tones';

interface KpiCardProps {
  label: string;
  value: string;
  hint: string;
  icon: LucideIcon;
  tone: Tone;
}

export const KpiCard: React.FC<KpiCardProps> = ({ label, value, hint, icon: Icon, tone }) => (
  <div className="glass-card flex flex-col justify-between rounded-2xl p-5">
    <div className="flex items-start justify-between gap-2">
      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ring-1 ${TONE_CLASSES[tone].icon}`}>
        <Icon className="h-5 w-5" />
      </div>
    </div>
    <div className="mt-4">
      <p className="text-3xl font-bold tracking-tight text-slate-900">{value}</p>
      <p className="mt-1 text-sm font-medium text-slate-700">{label}</p>
      <p className="text-xs text-slate-500">{hint}</p>
    </div>
  </div>
);

export default KpiCard;

