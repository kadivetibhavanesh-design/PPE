import React from 'react';
import { Eye, ShieldAlert, Timer, RotateCcw, Camera, CameraOff } from 'lucide-react';
import type { ViolationRecord, ViolationSeverityLevel, ViolationLifecycleStatus } from '@/types/violations';

interface ViolationRecordsTableProps {
  violations: ViolationRecord[];
  onSelectViolation: (violation: ViolationRecord) => void;
  onResetFilters: () => void;
  hasFilters: boolean;
}

const SEVERITY_CLASSES: Record<ViolationSeverityLevel, string> = {
  Critical: 'bg-rose-100 text-rose-800 border-rose-200',
  High: 'bg-amber-100 text-amber-800 border-amber-200',
  Medium: 'bg-blue-100 text-blue-800 border-blue-200',
};

const STATUS_CLASSES: Record<ViolationLifecycleStatus, string> = {
  Open: 'bg-rose-50 text-rose-700 border-rose-200',
  Ongoing: 'bg-red-50 text-red-700 border-red-200',
  Resolved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  Closed: 'bg-slate-100 text-slate-600 border-slate-200',
};

export const ViolationRecordsTable: React.FC<ViolationRecordsTableProps> = ({
  violations,
  onSelectViolation,
  onResetFilters,
  hasFilters,
}) => {
  return (
    <div className="glass-card overflow-hidden rounded-2xl">
      <div className="flex flex-col gap-2 border-b border-slate-200/80 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose-50 text-rose-600 ring-1 ring-rose-100">
            <ShieldAlert className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900">Safety Violation Records</h3>
            <p className="text-xs text-slate-500">
              Audit log of continuous PPE non-compliance events and resolution lifecycle.
            </p>
          </div>
        </div>
      </div>

      {violations.length === 0 ? (
        <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <h4 className="mt-3 text-sm font-semibold text-slate-800">No safety violations match the filters</h4>
          <p className="mt-1 max-w-sm text-xs text-slate-500">
            Try adjusting your search criteria or resetting filters to review recorded events.
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
                  Violation ID
                </th>
                <th scope="col" className="px-5 py-3.5">
                  Worker Tracking
                </th>
                <th scope="col" className="px-5 py-3.5">
                  PPE Category
                </th>
                <th scope="col" className="px-5 py-3.5 text-center">
                  Severity
                </th>
                <th scope="col" className="px-5 py-3.5">
                  First Detected
                </th>
                <th scope="col" className="px-5 py-3.5">
                  Duration
                </th>
                <th scope="col" className="px-5 py-3.5 text-center">
                  Evidence
                </th>
                <th scope="col" className="px-5 py-3.5 text-center">
                  Status
                </th>
                <th scope="col" className="px-5 py-3.5 text-right">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white/60">
              {violations.map((record) => {
                const severityClass = SEVERITY_CLASSES[record.severity] || 'bg-slate-100 text-slate-700';
                const statusClass = STATUS_CLASSES[record.status] || 'bg-slate-100 text-slate-700';
                const categories = record.ppeCategories && record.ppeCategories.length > 0
                  ? record.ppeCategories
                  : [record.ppeCategory];

                return (
                  <tr key={record.violationId} className="transition-colors hover:bg-slate-50/80">
                    {/* Violation ID */}
                    <td className="whitespace-nowrap px-5 py-4">
                      <span className="font-mono text-xs font-bold text-slate-800 bg-slate-100 px-2.5 py-1 rounded-lg border border-slate-200">
                        {record.violationId}
                      </span>
                    </td>

                    {/* Worker ID and Name */}
                    <td className="px-5 py-4">
                      <div className="flex flex-col">
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-xs font-semibold text-brand-700">
                            #{record.workerId.toString().padStart(2, '0')}
                          </span>
                          <span className="font-semibold text-slate-900">{record.workerName}</span>
                        </div>
                        <span className="text-[11px] text-slate-500">{record.workerRole}</span>
                      </div>
                    </td>

                    {/* PPE Categories */}
                    <td className="px-5 py-4 font-medium text-slate-800">
                      <div className="flex flex-wrap gap-1">
                        {categories.map((cat, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-semibold capitalize text-slate-800"
                          >
                            {cat.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </td>

                    {/* Severity */}
                    <td className="whitespace-nowrap px-5 py-4 text-center">
                      <span
                        className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider ${severityClass}`}
                      >
                        {record.severity}
                      </span>
                    </td>

                    {/* First Detected */}
                    <td className="whitespace-nowrap px-5 py-4 text-xs text-slate-600">
                      {record.firstDetected}
                    </td>

                    {/* Duration */}
                    <td className="whitespace-nowrap px-5 py-4">
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded-md">
                        <Timer className="h-3.5 w-3.5 text-slate-400" />
                        {record.durationSeconds}s
                      </span>
                    </td>

                    {/* Evidence Frame */}
                    <td className="whitespace-nowrap px-5 py-4 text-center">
                      {record.hasEvidence ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                          <Camera className="h-3 w-3 text-emerald-600" />
                          Captured
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
                          <CameraOff className="h-3 w-3 text-slate-400" />
                          None
                        </span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="whitespace-nowrap px-5 py-4 text-center">
                      <span
                        className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusClass}`}
                      >
                        {record.status}
                      </span>
                    </td>

                    {/* Action */}
                    <td className="whitespace-nowrap px-5 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => onSelectViolation(record)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-xs transition hover:border-brand-500 hover:bg-brand-50/50 hover:text-brand-700 cursor-pointer"
                        title={`View violation details for ${record.violationId}`}
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

export default ViolationRecordsTable;

