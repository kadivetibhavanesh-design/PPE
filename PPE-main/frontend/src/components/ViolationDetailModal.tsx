import React from 'react';
import {
  Dialog,
  DialogContent,
  IconButton,
} from '@mui/material';
import {
  X,
  ShieldAlert,
  Clock,
  MapPin,
  Briefcase,
  Timer,
  CheckCircle2,
  Check,
  Camera,
} from 'lucide-react';
import type {
  ViolationRecord,
  ViolationSeverityLevel,
  ViolationLifecycleStatus,
} from '@/types/violations';
import { evidenceService } from '@/services/evidenceService';

interface ViolationDetailModalProps {
  violation: ViolationRecord | null;
  open: boolean;
  onClose: () => void;
  onResolve: (violationId: string) => void;
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

export const ViolationDetailModal: React.FC<ViolationDetailModalProps> = ({
  violation,
  open,
  onClose,
  onResolve,
}) => {
  if (!violation) return null;

  const isResolvedOrClosed =
    violation.status === 'Resolved' || violation.status === 'Closed';
  const severityClass = SEVERITY_CLASSES[violation.severity];
  const statusClass = STATUS_CLASSES[violation.status];

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      slotProps={{
        paper: {
          className:
            'rounded-2xl border border-slate-200/80 shadow-2xl backdrop-blur-md bg-white/95 overflow-hidden',
          sx: { margin: { xs: 2, sm: 4 }, maxHeight: 'calc(100% - 32px)' },
        },
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between border-b border-slate-200/80 bg-slate-50/70 p-5 sm:p-6">
        <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-sm font-bold text-rose-700 bg-rose-50 px-2.5 py-1 rounded-xl border border-rose-200">
              {violation.violationId}
            </span>
            <h2 className="text-xl font-bold tracking-tight text-slate-900">
              Violation Details
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider ${severityClass}`}
            >
              {violation.severity}
            </span>
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${statusClass}`}
            >
              {violation.status}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <IconButton
            onClick={onClose}
            size="small"
            className="text-slate-400 hover:text-slate-700 hover:bg-slate-200/60"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </IconButton>
        </div>
      </div>

      <DialogContent className="space-y-6 p-5 sm:p-6 text-slate-800">
        {/* Worker Information */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 rounded-xl border border-slate-200/70 bg-slate-50/50 p-4">
          <div className="flex items-start gap-2.5">
            <span className="font-mono text-xs font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded-lg border border-brand-200 mt-0.5">
              #{violation.workerId.toString().padStart(2, '0')}
            </span>
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Worker</p>
              <p className="text-xs font-semibold text-slate-900">{violation.workerName}</p>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <Briefcase className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Role</p>
              <p className="text-xs font-semibold text-slate-800">{violation.workerRole}</p>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <MapPin className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Detection Zone</p>
              <p className="text-xs font-semibold text-slate-800">{violation.workerZone}</p>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <Clock className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">First Detected</p>
              <p className="text-xs font-semibold text-slate-800">{violation.firstDetected}</p>
            </div>
          </div>
        </div>

        {/* Violation Metrics Highlight */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium text-slate-500">PPE Category</p>
            <p className="mt-1 text-base font-bold text-slate-900">{violation.ppeCategory}</p>
            <p className="mt-0.5 text-[11px] text-slate-400">
              Severity standard: {violation.severity}
            </p>
          </div>

          <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-4">
            <p className="text-xs font-medium text-rose-800 flex items-center gap-1">
              <Timer className="h-3.5 w-3.5" />
              Continuous Violation Duration
            </p>
            <p className="mt-1 text-base font-bold text-rose-700">
              {violation.durationSeconds}s continuous
            </p>
            <p className="mt-0.5 text-[11px] text-rose-600">
              Alarm threshold exceeded ({'>'} 5.0s)
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium text-slate-500">Lifecycle State</p>
            <p className="mt-1 text-base font-bold text-slate-900">{violation.status}</p>
            <p className="mt-0.5 text-[11px] text-slate-400">
              {isResolvedOrClosed ? 'Resolved and safe' : 'Active investigation'}
            </p>
          </div>
        </div>

        {/* Detailed Description */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
          <div className="flex items-center gap-2 text-slate-900">
            <ShieldAlert className="h-4 w-4 text-rose-600" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Violation Narrative & Sensor Observation
            </h3>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-700 bg-white p-3 rounded-lg border border-slate-200/80">
            {violation.description}
          </p>
        </div>

        {/* Evidence Snapshot */}
        {violation.hasEvidence && (
          <div className="rounded-xl border border-indigo-200 bg-indigo-50/30 p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 text-indigo-900">
                <Camera className="h-4 w-4 text-indigo-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-800">
                  Captured Camera Frame Evidence
                </h3>
              </div>
              <span className="text-[11px] font-medium text-indigo-600">
                Annotated Snapshot Saved
              </span>
            </div>
            <div className="overflow-hidden rounded-lg border border-indigo-100 bg-black/5 flex items-center justify-center max-h-64">
              <img
                src={evidenceService.getEvidenceImageUrl(violation.violationId)}
                alt={`Evidence snapshot for ${violation.violationId}`}
                className="max-h-60 w-auto object-contain rounded"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
            </div>
          </div>
        )}
      </DialogContent>

      {/* Footer Actions */}
      <div className="border-t border-slate-200/80 bg-slate-50/50 px-5 py-3.5 sm:px-6 flex items-center justify-between gap-3">
        <div>
          {isResolvedOrClosed ? (
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-xl">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              Status: {violation.status}
            </span>
          ) : (
            <button
              type="button"
              onClick={() => onResolve(violation.violationId)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-xs hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 transition cursor-pointer"
            >
              <Check className="h-4 w-4" />
              Resolve Violation
            </button>
          )}
        </div>

        <button
          type="button"
          onClick={onClose}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 focus:outline-none"
        >
          Close
        </button>
      </div>
    </Dialog>
  );
};

export default ViolationDetailModal;

