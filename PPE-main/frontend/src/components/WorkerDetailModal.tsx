import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  X,
  HardHat,
  Shield,
  Hand,
  Glasses,
  ShieldCheck,
  Footprints,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Timer,
  Camera,
  ExternalLink,
  Layers,
} from 'lucide-react';
import type {
  WorkerItem,
  PpeCategoryName,
  PpeComplianceState,
  WorkerTrackingStatus,
  WorkerComplianceStatus,
} from '@/types/workers';
import type { EvidenceRecord } from '@/types/evidence';
import { evidenceService } from '@/services/evidenceService';
import StatusPill from '@/components/StatusPill';

interface WorkerDetailModalProps {
  worker: WorkerItem | null;
  open: boolean;
  onClose: () => void;
}

const PPE_ICONS: Record<PpeCategoryName, React.ComponentType<{ className?: string }>> = {
  Hardhat: HardHat,
  'Safety Vest': Shield,
  'Safety Gloves': Hand,
  'Eye Protection': Glasses,
  'Protective Mask': ShieldCheck,
  'Safety Footwear': Footprints,
};

const PPE_STATUS_TONES: Record<PpeComplianceState, 'green' | 'red' | 'slate' | 'amber'> = {
  Compliant: 'green',
  'Non-Compliant': 'red',
  Missing: 'red',
  Uncertain: 'amber',
  'Not Detected': 'slate',
  'Not Verifiable': 'slate',
};

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

export const WorkerDetailModal: React.FC<WorkerDetailModalProps> = ({
  worker,
  open,
  onClose,
}) => {
  const [workerIncidents, setWorkerIncidents] = useState<EvidenceRecord[]>([]);
  const [isLoadingIncidents, setIsLoadingIncidents] = useState<boolean>(false);

  useEffect(() => {
    if (worker && open) {
      setIsLoadingIncidents(true);
      evidenceService
        .getEvidenceList({ worker_track_id: worker.workerId })
        .then((records) => setWorkerIncidents(records))
        .catch(() => setWorkerIncidents([]))
        .finally(() => setIsLoadingIncidents(false));
    } else {
      setWorkerIncidents([]);
    }
  }, [worker, open]);

  if (!worker) return null;

  const trackingTone = TRACKING_TONES[worker.trackingStatus] || 'slate';
  const complianceTone = COMPLIANCE_TONES[worker.complianceStatus] || 'slate';
  const hasViolations = worker.activeViolations.length > 0;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      slotProps={{
        paper: {
          className: 'rounded-2xl border border-slate-200/80 shadow-2xl backdrop-blur-md bg-white/95 overflow-hidden',
          sx: { margin: { xs: 2, sm: 4 }, maxHeight: 'calc(100% - 32px)' },
        },
      }}
    >
      {/* Modal Header */}
      <div className="flex items-start justify-between border-b border-slate-200/80 bg-slate-50/70 p-5 sm:p-6">
        <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-3">
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-sm font-bold text-slate-800 bg-slate-100 px-2.5 py-1 rounded-xl border border-slate-200">
              Worker #{worker.workerId.toString().padStart(2, '0')}
            </span>
            <span className="text-xs text-slate-500 font-mono">
              ByteTrack ID: #{worker.workerId}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill tone={trackingTone}>
              {worker.trackingStatus === 'Active' ? 'In Camera View' : 'Lost / Out of Frame'}
            </StatusPill>
            <StatusPill tone={complianceTone}>{worker.complianceStatus}</StatusPill>
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
        {/* Tracking & Telemetry Lifecycle Info */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 rounded-xl border border-slate-200/70 bg-slate-50/50 p-4">
          <div className="flex items-start gap-2.5">
            <Layers className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Tracking Identity</p>
              <p className="text-xs font-semibold text-slate-800">ByteTrack #{worker.workerId}</p>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <Camera className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Surveillance View</p>
              <p className="text-xs font-semibold text-slate-800">{worker.zone}</p>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <Clock className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">First Detected</p>
              <p className="text-xs font-semibold text-slate-800">{worker.firstSeen}</p>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <Clock className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
            <div>
              <p className="text-[11px] font-medium text-slate-400 uppercase tracking-wide">Last Seen</p>
              <p className="text-xs font-semibold text-slate-800">{worker.lastSeen}</p>
            </div>
          </div>
        </div>

        {/* Active Violations Section */}
        {hasViolations ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-4">
            <div className="flex items-center gap-2 text-rose-800">
              <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0" />
              <h3 className="text-sm font-bold">Active Safety Violations ({worker.activeViolations.length})</h3>
            </div>
            <div className="mt-3 space-y-2">
              {worker.activeViolations.map((v) => (
                <div
                  key={v.violationId}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 rounded-lg border border-rose-200/80 bg-white/90 p-3 shadow-2xs"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="rounded-md bg-rose-100 px-2 py-0.5 text-xs font-bold text-rose-800 uppercase tracking-wider">
                      {v.severity}
                    </span>
                    <div>
                      <span className="text-xs font-semibold text-slate-900">
                        Missing or Non-Compliant {v.category}
                      </span>
                      <span className="ml-2 font-mono text-[11px] text-slate-500">
                        ID: {v.violationId}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-700 bg-rose-100/70 px-2.5 py-1 rounded-md">
                      <Timer className="h-3.5 w-3.5" />
                      {v.durationSeconds}s continuous
                    </span>
                    <span className="text-[11px] text-slate-500">
                      Status: {v.detectedAt}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 text-emerald-800">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
            <div>
              <p className="text-xs font-bold text-emerald-900">Worker is fully compliant</p>
              <p className="text-[11px] text-emerald-700">
                All mandatory industrial PPE standards are verified and compliant in the camera view.
              </p>
            </div>
          </div>
        )}

        {/* 6 PPE Categories Breakdown */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
              Individual PPE Category Compliance (6 Standards)
            </h3>
            <span className="text-xs text-slate-500">Real-time object detector analysis</span>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {worker.ppeBreakdown.map((item) => {
              const Icon = PPE_ICONS[item.category] || Shield;
              const tone = PPE_STATUS_TONES[item.status] || 'slate';

              return (
                <div
                  key={item.category}
                  className={`flex flex-col justify-between rounded-xl border p-3.5 transition-all ${
                    item.status === 'Compliant'
                      ? 'border-emerald-200/70 bg-emerald-50/20'
                      : item.status === 'Missing' || item.status === 'Non-Compliant'
                      ? 'border-rose-200 bg-rose-50/30'
                      : item.status === 'Uncertain'
                      ? 'border-amber-200 bg-amber-50/30'
                      : 'border-slate-200 bg-slate-50/50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div
                        className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                          item.status === 'Compliant'
                            ? 'bg-emerald-100 text-emerald-700'
                            : item.status === 'Missing' || item.status === 'Non-Compliant'
                            ? 'bg-rose-100 text-rose-700'
                            : item.status === 'Uncertain'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-slate-200 text-slate-600'
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-slate-900">{item.category}</h4>
                        {item.confidence !== undefined && (
                          <span className="text-[10px] text-slate-400">
                            {item.confidence}% model confidence
                          </span>
                        )}
                      </div>
                    </div>
                    <StatusPill tone={tone}>{item.status}</StatusPill>
                  </div>

                  {item.notes && (
                    <div className="mt-2.5 rounded-md bg-white/80 p-2 text-[11px] leading-relaxed text-slate-600 border border-slate-100">
                      {item.notes}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Worker Incident History & Evidence Records */}
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800 flex items-center gap-2">
              <Camera className="h-4 w-4 text-indigo-600" />
              Recorded Incident Evidence for Worker #{worker.workerId}
            </h3>
            <span className="text-xs text-slate-500">
              {workerIncidents.length} recorded incident{workerIncidents.length === 1 ? '' : 's'}
            </span>
          </div>

          {isLoadingIncidents ? (
            <div className="flex items-center justify-center p-6 text-xs text-slate-500 gap-2">
              <CircularProgress size={16} />
              Loading incident history...
            </div>
          ) : workerIncidents.length === 0 ? (
            <p className="text-xs text-slate-400 italic py-2">
              No historical safety violation incidents recorded for this worker tracking ID.
            </p>
          ) : (
            <div className="divide-y divide-slate-100 max-h-48 overflow-y-auto">
              {workerIncidents.map((inc) => (
                <div key={inc.event_id} className="py-2.5 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                      {inc.event_id}
                    </span>
                    <span className="capitalize font-semibold text-slate-800">
                      {inc.ppe_category.replace(/_/g, ' ')}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      {new Date((inc.first_detected_timestamp || 0) * 1000).toLocaleString()}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                      inc.status === 'resolved' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
                    }`}>
                      {inc.status || 'open'}
                    </span>
                    {(inc.image_filename || inc.evidence_image_filename) && (
                      <a
                        href={evidenceService.getEvidenceImageUrl(inc.event_id)}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded bg-indigo-50 px-2 py-1 text-[11px] font-bold text-indigo-700 hover:bg-indigo-100"
                      >
                        <Camera className="h-3 w-3" />
                        Frame
                        <ExternalLink className="h-2.5 w-2.5" />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>

      {/* Modal Actions */}
      <div className="border-t border-slate-200/80 bg-slate-50/50 px-5 py-3.5 sm:px-6 flex justify-end">
        <button
          type="button"
          onClick={onClose}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 focus:outline-none cursor-pointer"
        >
          Close
        </button>
      </div>
    </Dialog>
  );
};

export default WorkerDetailModal;

