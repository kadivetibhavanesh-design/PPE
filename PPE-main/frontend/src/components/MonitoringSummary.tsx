import React from 'react';
import type { Tone } from '@/types/overview';
import { TONE_CLASSES } from '@/utils/tones';
import SectionCard from '@/components/SectionCard';

export interface SummaryRow {
  label: string;
  value: number;
  tone: Tone;
}

interface MonitoringSummaryProps {
  rows: SummaryRow[];
}

export const MonitoringSummary: React.FC<MonitoringSummaryProps> = ({ rows }) => (
  <SectionCard title="Monitoring Summary" subtitle="Live workers in current view">
    <ul className="divide-y divide-slate-100">
      {rows.map((row) => (
        <li key={row.label} className="flex items-center justify-between py-3">
          <span className="flex items-center gap-2.5 text-sm text-slate-700">
            <span className={`h-2.5 w-2.5 rounded-full ${TONE_CLASSES[row.tone].dot}`} />
            {row.label}
          </span>
          <span className="text-lg font-semibold text-slate-900">{row.value}</span>
        </li>
      ))}
    </ul>
  </SectionCard>
);

export default MonitoringSummary;
