import React from 'react';
import { Eye, AlertTriangle, Users, RotateCcw } from 'lucide-react';
import type { WorkerItem, WorkerTrackingStatus, WorkerComplianceStatus } from '@/types/workers';
import StatusPill from '@/components/StatusPill';

interface WorkerDirectoryTableProps {
  workers: WorkerItem[];
  onSelectWorker: (worker: WorkerItem) => void;
  onResetFilters: () => void;
  hasFilters: boolean;
}

const TRACKING_TONES: Record<WorkerTrackingStatus, 'blue' | 'amber' | 'slate'> = {
  Active: 'blue',
  Missing: 'amber',
  Left: 'slate',
};

const COMPLIANCE_TONES: Record<WorkerComplianceStatus, 'green' | 'red' | 'amber'> = {
  Compliant: 'green',
  'Non-Compliant': 'red',
  'Needs Review': 'amber',
};

export const WorkerDirectoryTable: React.FC<WorkerDirectoryTableProps> = ({
  workers,
  onSelectWorker,
  onResetFilters,
  hasFilters,
}) => {
  return (
    <div className="glass-card overflow-hidden rounded-2xl">
      <div className="flex flex-col gap-2 border-b border-slate-200/80 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Worker Directory</h3>
          <p className="text-xs text-slate-500">
            Real-time track history, compliance status, and telemetry per worker.
          </p>
        </div>
      </div>

      {workers.length === 0 ? (
        <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
            <Users className="h-6 w-6" />
          </div>
          <h4 className="mt-3 text-sm font-semibold text-slate-800">
            {hasFilters ? 'No workers match your search or filter' : 'No workers detected'}
          </h4>
          <p className="mt-1 max-w-sm text-xs text-slate-500">
            {hasFilters
              ? 'Try adjusting your search keyword or clearing the active status filters to see all monitored workers.'
              : 'Position workers in front of the camera and start live monitoring to track personnel in real time.'}
          </p>
          {hasFilters && (
            <button
              type="button"
              onClick={onResetFilters}
              className="mt-4 inline-flex items-center gap-1.5 rounded-xl border border-brand-200 bg-brand-50 px-3.5 py-2 text-xs font-semibold text-brand-700 transition hover:bg-brand-100"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset all filters
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50/75 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th scope="col" className="px-5 py-3.5">
                  Worker Tracking ID
                </th>
                <th scope="col" className="px-5 py-3.5">
                  Presence Status
                </th>
                <th scope="col" className="px-5 py-3.5">
                  PPE Compliance
                </th>
                <th scope="col" className="px-5 py-3.5">
                  Missing PPE
                </th>
                <th scope="col" className="px-5 py-3.5 text-center">
                  Active Incidents
                </th>
                <th scope="col" className="px-5 py-3.5">
                  Last Detection Time
                </th>
                <th scope="col" className="px-5 py-3.5 text-right">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white/60">
              {workers.map((worker) => {
                const trackingTone = TRACKING_TONES[worker.trackingStatus] || 'slate';
                const complianceTone = COMPLIANCE_TONES[worker.complianceStatus] || 'slate';
                const hasViolations = worker.activeViolations.length > 0;
                const incidentCount = worker.activeIncidentCount ?? worker.activeViolations.length;

                return (
                  <tr
                    key={worker.workerId}
                    className="transition-colors hover:bg-slate-50/80"
                  >
                    {/* Worker ID / Track ID */}
                    <td className="whitespace-nowrap px-5 py-4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2.5 py-1 rounded-lg border border-slate-200">
                          Worker #{worker.workerId.toString().padStart(2, '0')}
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono">
                          (ByteTrack #{worker.workerId})
                        </span>
                      </div>
                    </td>

                    {/* Presence Status */}
                    <td className="whitespace-nowrap px-5 py-4">
                      <StatusPill tone={trackingTone}>
                        {worker.trackingStatus === 'Active' ? 'In Camera View' : 'Lost / Out of Frame'}
                      </StatusPill>
                    </td>

                    {/* PPE Compliance Status */}
                    <td className="whitespace-nowrap px-5 py-4">
                      <StatusPill tone={complianceTone}>
                        {worker.complianceStatus}
                      </StatusPill>
                    </td>

                    {/* Missing PPE */}
                    <td className="px-5 py-4">
                      {hasViolations ? (
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {worker.activeViolations.map((v) => (
                            <span
                              key={v.violationId}
                              className="inline-flex items-center gap-1 rounded-md border border-rose-200 bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700"
                            >
                              <AlertTriangle className="h-3 w-3 shrink-0" />
                              {v.category}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">None (Verified)</span>
                      )}
                    </td>

                    {/* Active Incidents Count */}
                    <td className="whitespace-nowrap px-5 py-4 text-center">
                      <span
                        className={`inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-xs font-bold ${
                          incidentCount > 0
                            ? 'bg-rose-100 text-rose-800 border border-rose-200'
                            : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {incidentCount}
                      </span>
                    </td>

                    {/* Last Detection Time */}
                    <td className="whitespace-nowrap px-5 py-4 text-xs font-medium text-slate-700">
                      {worker.lastSeen}
                    </td>

                    {/* Action */}
                    <td className="whitespace-nowrap px-5 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => onSelectWorker(worker)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-xs transition hover:border-brand-500 hover:bg-brand-50/50 hover:text-brand-700"
                        title={`View details for worker #${worker.workerId}`}
                      >
                        <Eye className="h-3.5 w-3.5" />
                        View Details
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default WorkerDirectoryTable;

