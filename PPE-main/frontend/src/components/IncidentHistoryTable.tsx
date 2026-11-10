import React from 'react';
import {
  Eye,
  Camera,
  CameraOff,
  User,
  Clock,
  HardHat,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import type { EvidenceRecord } from '@/types/evidence';
import {
  formatTimestamp,
  SEVERITY_BADGES,
  STATUS_BADGES,
} from '@/utils/evidenceUtils';

interface IncidentHistoryTableProps {
  evidenceList: EvidenceRecord[];
  onSelectEvidence: (item: EvidenceRecord) => void;
  isFiltered: boolean;
  onClearFilters: () => void;
  currentPage?: number;
  totalPages?: number;
  pageSize?: number;
  totalFilteredCount?: number;
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
}

export const IncidentHistoryTable: React.FC<IncidentHistoryTableProps> = ({
  evidenceList,
  onSelectEvidence,
  isFiltered,
  onClearFilters,
  currentPage = 1,
  totalPages = 1,
  pageSize = 10,
  totalFilteredCount = 0,
  onPageChange,
  onPageSizeChange,
}) => {
  if (evidenceList.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-12 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400 mb-4">
          <ShieldAlert className="h-7 w-7 text-slate-400" />
        </div>
        <h3 className="text-base font-bold text-slate-800">
          {isFiltered ? 'No Matching Incidents Found' : 'No Incident Evidence Stored'}
        </h3>
        <p className="mx-auto mt-1.5 max-w-md text-xs text-slate-500">
          {isFiltered
            ? 'No incident evidence matches your current search or filter criteria. Try broadening your filters.'
            : 'No confirmed PPE violation events have been recorded yet. When a confirmed violation occurs during live monitoring, an annotated camera frame and audit metadata will be captured and saved here.'}
        </p>
        {isFiltered && (
          <button
            onClick={onClearFilters}
            className="mt-4 inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            Reset Filters
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden rounded-2xl border border-slate-200/90 shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200/80 bg-slate-50/80 font-semibold text-slate-600">
              <th className="py-3.5 pl-5 pr-3">Event ID</th>
              <th className="px-3 py-3.5">Worker</th>
              <th className="px-3 py-3.5">PPE Category</th>
              <th className="px-3 py-3.5">Severity</th>
              <th className="px-3 py-3.5">First Detected</th>
              <th className="px-3 py-3.5">Resolution Time</th>
              <th className="px-3 py-3.5">Status</th>
              <th className="px-3 py-3.5 text-center">Evidence Frame</th>
              <th className="py-3.5 pl-3 pr-5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {evidenceList.map((item) => {
              const severityKey = (item.severity || 'unclassified').toLowerCase();
              const statusKey = (item.status || item.event_status || 'open').toLowerCase();
              const hasImage = Boolean(
                item.image_filename || item.evidence_image_filename
              );

              return (
                <tr
                  key={item.event_id}
                  className="transition-colors hover:bg-slate-50/70"
                >
                  {/* Event ID */}
                  <td className="py-3 pl-5 pr-3 font-mono font-bold text-slate-900">
                    <span className="rounded-lg bg-rose-50 px-2 py-1 text-rose-700 border border-rose-200">
                      {item.event_id}
                    </span>
                  </td>

                  {/* Worker Track ID */}
                  <td className="px-3 py-3 font-semibold text-slate-900">
                    <span className="inline-flex items-center gap-1.5">
                      <User className="h-3.5 w-3.5 text-slate-500" />
                      Worker #{item.worker_track_id}
                    </span>
                  </td>

                  {/* PPE Category */}
                  <td className="px-3 py-3">
                    <span className="inline-flex items-center gap-1.5 font-medium capitalize text-slate-800">
                      <HardHat className="h-3.5 w-3.5 text-slate-500" />
                      {item.ppe_category.replace(/_/g, ' ')}
                    </span>
                  </td>

                  {/* Severity */}
                  <td className="px-3 py-3">
                    <span
                      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
                        SEVERITY_BADGES[severityKey] || SEVERITY_BADGES.unclassified
                      }`}
                    >
                      {item.severity}
                    </span>
                  </td>

                  {/* First Detected */}
                  <td className="px-3 py-3 text-slate-600">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3 text-slate-400" />
                      {formatTimestamp(item.first_detected_timestamp)}
                    </span>
                  </td>

                  {/* Resolution Time */}
                  <td className="px-3 py-3 text-slate-600">
                    {item.resolution_timestamp ? (
                      <span className="text-emerald-700 font-medium">
                        {formatTimestamp(item.resolution_timestamp)}
                      </span>
                    ) : (
                      <span className="text-amber-700 font-medium">
                        Ongoing / Unresolved
                      </span>
                    )}
                  </td>

                  {/* Event Status */}
                  <td className="px-3 py-3">
                    <span
                      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${
                        STATUS_BADGES[statusKey] || STATUS_BADGES.open
                      }`}
                    >
                      {item.status || item.event_status}
                    </span>
                  </td>

                  {/* Evidence Frame Available */}
                  <td className="px-3 py-3 text-center">
                    {hasImage ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-[11px] font-semibold text-indigo-700">
                        <Camera className="h-3 w-3 text-indigo-600" />
                        Captured
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-500">
                        <CameraOff className="h-3 w-3 text-slate-400" />
                        No Frame
                      </span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="py-3 pl-3 pr-5 text-right">
                    <button
                      onClick={() => onSelectEvidence(item)}
                      className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 cursor-pointer"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      <span>Details</span>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {onPageChange && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-slate-200/80 bg-slate-50/70 px-5 py-3 text-xs text-slate-600">
          <div className="flex items-center gap-2">
            <span>
              Showing <span className="font-semibold text-slate-900">{evidenceList.length}</span> of{' '}
              <span className="font-semibold text-slate-900">{totalFilteredCount || evidenceList.length}</span> incidents
            </span>
            {onPageSizeChange && (
              <div className="flex items-center gap-1.5 ml-4">
                <label htmlFor="inc-page-size" className="text-slate-500">Per page:</label>
                <select
                  id="inc-page-size"
                  value={pageSize}
                  onChange={(e) => onPageSizeChange(Number(e.target.value))}
                  className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-2xs"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-2xs transition hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Previous
            </button>
            <span className="px-2 font-medium text-slate-700">
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-2xs transition hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default IncidentHistoryTable;
