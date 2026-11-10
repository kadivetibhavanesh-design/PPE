import React from 'react';
import { Eye, ShieldCheck, Users } from 'lucide-react';
import type { WorkerComplianceRow, ComplianceStandardStatus } from '@/types/compliance';
import StatusPill from '@/components/StatusPill';

interface WorkerComplianceTableProps {
  rows: WorkerComplianceRow[];
  onSelectWorker: (workerId: number) => void;
}

const STATUS_TONES: Record<ComplianceStandardStatus, 'green' | 'red' | 'amber' | 'slate'> = {
  Compliant: 'green',
  'Non-Compliant': 'red',
  'Needs Review': 'amber',
  Uncertain: 'amber',
  'Not Verifiable': 'slate',
};

const CompactCategoryBadge: React.FC<{ status: ComplianceStandardStatus }> = ({ status }) => {
  if (status === 'Not Verifiable') {
    return (
      <span className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-medium text-slate-400 bg-slate-100 border border-slate-200" title="Standard not verifiable by active YOLO model profile">
        N/A
      </span>
    );
  }

  const tone = STATUS_TONES[status] || 'amber';
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap ${
        tone === 'green'
          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
          : tone === 'red'
          ? 'bg-rose-50 text-rose-700 border border-rose-200'
          : 'bg-amber-50 text-amber-700 border border-amber-200'
      }`}
    >
      {status === 'Compliant' ? 'Pass' : status === 'Non-Compliant' ? 'Fail' : 'Review'}
    </span>
  );
};

export const WorkerComplianceTable: React.FC<WorkerComplianceTableProps> = ({
  rows,
  onSelectWorker,
}) => {
  return (
    <div className="glass-card overflow-hidden rounded-2xl">
      <div className="flex flex-col gap-2 border-b border-slate-200/80 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600 ring-1 ring-brand-100">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900">Worker Compliance Matrix</h3>
            <p className="text-xs text-slate-500">
              Breakdown across all 6 mandatory PPE safety standards per tracked worker.
            </p>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
          <thead className="bg-slate-50/75 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <tr>
              <th scope="col" className="px-4 py-3.5">
                Worker ID
              </th>
              <th scope="col" className="px-4 py-3.5">
                Tracking Identity
              </th>
              <th scope="col" className="px-3 py-3.5 text-center">
                Hardhat
              </th>
              <th scope="col" className="px-3 py-3.5 text-center">
                Safety Vest
              </th>
              <th scope="col" className="px-3 py-3.5 text-center">
                Gloves
              </th>
              <th scope="col" className="px-3 py-3.5 text-center">
                Goggles
              </th>
              <th scope="col" className="px-3 py-3.5 text-center">
                Mask
              </th>
              <th scope="col" className="px-3 py-3.5 text-center">
                Safety Shoes
              </th>
              <th scope="col" className="px-4 py-3.5 text-center">
                Overall Status
              </th>
              <th scope="col" className="px-4 py-3.5 text-right">
                Action
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white/60">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-6 py-12 text-center">
                  <div className="flex flex-col items-center justify-center">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
                      <Users className="h-6 w-6" />
                    </div>
                    <p className="mt-3 text-sm font-semibold text-slate-700">No active workers detected</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Start live monitoring to evaluate personal protective equipment compliance in real time.
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              rows.map((row) => {
              const overallTone = STATUS_TONES[row.overallStatus] || 'green';

              return (
                <tr key={row.workerId} className="transition-colors hover:bg-slate-50/80">
                  {/* Worker ID */}
                  <td className="whitespace-nowrap px-4 py-3.5">
                    <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2.5 py-1 rounded-lg border border-slate-200">
                      #{row.workerId.toString().padStart(2, '0')}
                    </span>
                  </td>

                  {/* Tracking Identity */}
                  <td className="px-4 py-3.5">
                    <div className="flex flex-col">
                      <span className="font-semibold text-slate-900">{row.name}</span>
                      <span className="text-xs text-slate-500">ByteTrack Track #{row.workerId}</span>
                    </div>
                  </td>

                  {/* 6 PPE Category columns */}
                  <td className="px-3 py-3.5 text-center">
                    <CompactCategoryBadge status={row.hardhat} />
                  </td>
                  <td className="px-3 py-3.5 text-center">
                    <CompactCategoryBadge status={row.safetyVest} />
                  </td>
                  <td className="px-3 py-3.5 text-center">
                    <CompactCategoryBadge status={row.gloves} />
                  </td>
                  <td className="px-3 py-3.5 text-center">
                    <CompactCategoryBadge status={row.goggles} />
                  </td>
                  <td className="px-3 py-3.5 text-center">
                    <CompactCategoryBadge status={row.mask} />
                  </td>
                  <td className="px-3 py-3.5 text-center">
                    <CompactCategoryBadge status={row.safetyShoes} />
                  </td>

                  {/* Overall Status */}
                  <td className="whitespace-nowrap px-4 py-3.5 text-center">
                    <StatusPill tone={overallTone}>
                      {row.overallStatus}
                    </StatusPill>
                  </td>

                  {/* Action */}
                  <td className="whitespace-nowrap px-4 py-3.5 text-right">
                    <button
                      type="button"
                      onClick={() => onSelectWorker(row.workerId)}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-xs transition hover:border-brand-500 hover:bg-brand-50/50 hover:text-brand-700"
                      title={`View inspection details for worker #${row.workerId}`}
                    >
                      <Eye className="h-3.5 w-3.5" />
                      View Details
                    </button>
                  </td>
                </tr>
              );
            }))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default WorkerComplianceTable;

