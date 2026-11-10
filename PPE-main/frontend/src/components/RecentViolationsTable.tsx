import React from 'react';
import { CheckCircle2, Camera, Clock } from 'lucide-react';
import type { DemoViolation, Tone, ViolationSeverity, ViolationStatus } from '@/types/overview';
import { TONE_CLASSES } from '@/utils/tones';
import SectionCard from '@/components/SectionCard';

const SEVERITY_TONE: Record<ViolationSeverity, Tone> = { Critical: 'red', High: 'amber', Medium: 'blue' };
const STATUS_TONE: Record<ViolationStatus, Tone> = { Open: 'red', Ongoing: 'red', Resolved: 'green' };

const Pill: React.FC<{ tone: Tone; children: React.ReactNode }> = ({ tone, children }) => (
  <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONE_CLASSES[tone].badge}`}>
    {children}
  </span>
);

interface RecentViolationsTableProps {
  rows: DemoViolation[];
}

export const RecentViolationsTable: React.FC<RecentViolationsTableProps> = ({ rows }) => (
  <SectionCard title="Recent Violations" subtitle="Audit log of active and recently confirmed events">
    {rows.length > 0 ? (
      <div className="-mx-2 overflow-x-auto px-2">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2.5 pr-3 font-semibold">Incident ID</th>
              <th className="py-2.5 pr-3 font-semibold">Worker ID</th>
              <th className="py-2.5 pr-3 font-semibold">Violation Categories</th>
              <th className="py-2.5 pr-3 font-semibold">Severity</th>
              <th className="py-2.5 pr-3 font-semibold">Time</th>
              <th className="py-2.5 pr-3 font-semibold">Status</th>
              <th className="py-2.5 font-semibold text-center">Evidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row) => {
              const categories = row.ppeCategories && row.ppeCategories.length > 0
                ? row.ppeCategories
                : [row.ppeCategory];

              return (
                <tr key={row.eventId} className="hover:bg-slate-50/60 transition-colors">
                  <td className="py-3 pr-3 font-mono font-bold text-xs text-rose-700">
                    <span className="rounded-lg bg-rose-50 px-2 py-1 border border-rose-200">
                      {row.eventId}
                    </span>
                  </td>
                  <td className="py-3 pr-3 font-medium text-slate-900">Worker #{row.workerId}</td>
                  <td className="py-3 pr-3 text-slate-700">
                    <div className="flex flex-wrap gap-1">
                      {categories.map((cat, i) => (
                        <span
                          key={i}
                          className="inline-flex rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize text-slate-700"
                        >
                          {cat.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 pr-3">
                    <Pill tone={SEVERITY_TONE[row.severity] || 'red'}>{row.severity}</Pill>
                  </td>
                  <td className="py-3 pr-3 text-xs text-slate-600">
                    <span className="inline-flex items-center gap-1 font-mono">
                      <Clock className="h-3 w-3 text-slate-400" />
                      {row.time || 'Recently'}
                    </span>
                  </td>
                  <td className="py-3 pr-3">
                    <Pill tone={STATUS_TONE[row.status] || 'red'}>{row.status}</Pill>
                  </td>
                  <td className="py-3 text-center">
                    {row.hasEvidence ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-indigo-700">
                        <Camera className="h-3 w-3 text-indigo-600" />
                        Captured
                      </span>
                    ) : (
                      <span className="text-slate-400 text-xs">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    ) : (
      <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500">
        <CheckCircle2 className="h-8 w-8 text-emerald-500" />
        <p className="mt-2 text-xs font-semibold text-slate-700">No violations recorded</p>
        <p className="text-[11px] text-slate-400">
          No confirmed PPE violations have occurred in the current session.
        </p>
      </div>
    )}
  </SectionCard>
);

export default RecentViolationsTable;
