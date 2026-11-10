import React, { useState } from 'react';
import { Dialog, IconButton } from '@mui/material';
import {
  X,
  ShieldAlert,
  User,
  Clock,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Image as ImageIcon,
  ImageOff,
  HardHat,
  FolderOpen,
} from 'lucide-react';
import type { EvidenceRecord } from '@/types/evidence';
import { evidenceService } from '@/services/evidenceService';
import {
  formatTimestamp,
  formatDuration,
  SEVERITY_BADGES,
  STATUS_BADGES,
} from '@/utils/evidenceUtils';

interface IncidentDetailsModalProps {
  evidence: EvidenceRecord | null;
  open: boolean;
  onClose: () => void;
}

export const IncidentDetailsModal: React.FC<IncidentDetailsModalProps> = ({
  evidence,
  open,
  onClose,
}) => {
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  if (!evidence) return null;

  const severityKey = (evidence.severity || 'unclassified').toLowerCase();
  const statusKey = (evidence.status || evidence.event_status || 'open').toLowerCase();

  const severityBadgeClass =
    SEVERITY_BADGES[severityKey] || SEVERITY_BADGES.unclassified;
  const statusBadgeClass = STATUS_BADGES[statusKey] || STATUS_BADGES.open;

  const hasImageFilename = Boolean(
    evidence.image_filename || evidence.evidence_image_filename
  );
  const imageUrl = hasImageFilename
    ? evidenceService.getEvidenceImageUrl(evidence.event_id)
    : null;

  const isResolved = statusKey === 'resolved' || statusKey === 'closed';

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      slotProps={{
        paper: {
          className:
            'rounded-2xl border border-slate-200/90 shadow-2xl backdrop-blur-md bg-white/95 overflow-hidden',
          sx: { margin: { xs: 2, sm: 4 }, maxHeight: 'calc(100% - 32px)' },
        },
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between border-b border-slate-200/80 bg-slate-50/70 p-5 sm:p-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-sm font-bold text-rose-700 bg-rose-50 px-2.5 py-1 rounded-xl border border-rose-200 shadow-sm">
              {evidence.event_id}
            </span>
            <h2 className="text-xl font-bold tracking-tight text-slate-900">
              Incident Evidence
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider ${severityBadgeClass}`}
            >
              {evidence.severity}
            </span>
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize ${statusBadgeClass}`}
            >
              {evidence.status || evidence.event_status}
            </span>
          </div>
        </div>
        <IconButton
          onClick={onClose}
          size="small"
          className="text-slate-400 hover:text-slate-700"
          aria-label="Close dialog"
        >
          <X className="h-5 w-5" />
        </IconButton>
      </div>

      {/* Modal Content */}
      <div className="space-y-6 overflow-y-auto p-5 sm:p-6">
        {/* Evidence Frame Preview */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <ImageIcon className="h-4 w-4 text-indigo-600" />
              Captured Camera Snapshot (YOLO Overlaid)
            </h3>
            {hasImageFilename && !imageError && imageUrl && (
              <a
                href={imageUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition"
              >
                <span>Open Raw Image</span>
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>

          <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-slate-950 flex items-center justify-center min-h-[260px] sm:min-h-[340px]">
            {hasImageFilename && !imageError && imageUrl ? (
              <>
                {!imageLoaded && (
                  <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80 text-slate-300 text-xs">
                    <div className="flex flex-col items-center gap-2">
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
                      <span>Loading evidence frame...</span>
                    </div>
                  </div>
                )}
                <img
                  src={imageUrl}
                  alt={`Evidence for incident ${evidence.event_id}`}
                  className={`max-h-[440px] w-full object-contain transition-opacity duration-300 ${
                    imageLoaded ? 'opacity-100' : 'opacity-0'
                  }`}
                  onLoad={() => setImageLoaded(true)}
                  onError={() => setImageError(true)}
                />
              </>
            ) : (
              <div className="flex flex-col items-center justify-center p-8 text-center text-slate-400">
                <div className="rounded-full bg-slate-800/80 p-3 mb-2">
                  <ImageOff className="h-8 w-8 text-slate-400" />
                </div>
                <p className="text-sm font-semibold text-slate-300">
                  No Camera Frame Available
                </p>
                <p className="max-w-xs text-xs text-slate-400 mt-1">
                  {imageError
                    ? 'The image file could not be loaded from the local evidence storage.'
                    : 'This incident was recorded without an annotated camera snapshot.'}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Metadata Details Grid */}
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-slate-900">
            Event Audit Metadata
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {/* Worker */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-500 mb-1">
                <User className="h-3.5 w-3.5 text-slate-600" />
                <span>Worker Tracking ID</span>
              </div>
              <p className="text-sm font-bold text-slate-900">
                Worker #{evidence.worker_track_id}
              </p>
            </div>

            {/* PPE Category */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-500 mb-1">
                <HardHat className="h-3.5 w-3.5 text-slate-600" />
                <span>PPE Category</span>
              </div>
              <p className="text-sm font-bold capitalize text-slate-900">
                {evidence.ppe_category.replace(/_/g, ' ')}
              </p>
            </div>

            {/* Severity */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-500 mb-1">
                <ShieldAlert className="h-3.5 w-3.5 text-slate-600" />
                <span>Severity Level</span>
              </div>
              <p className="text-sm font-bold capitalize text-slate-900">
                {evidence.severity}
              </p>
            </div>

            {/* First Detected */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-500 mb-1">
                <Clock className="h-3.5 w-3.5 text-slate-600" />
                <span>First Detected</span>
              </div>
              <p className="text-xs font-semibold text-slate-800">
                {formatTimestamp(evidence.first_detected_timestamp)}
              </p>
            </div>

            {/* Resolution Timestamp */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-500 mb-1">
                {isResolved ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <AlertCircle className="h-3.5 w-3.5 text-amber-600" />
                )}
                <span>Resolution Time</span>
              </div>
              <p className="text-xs font-semibold text-slate-800">
                {evidence.resolution_timestamp
                  ? formatTimestamp(evidence.resolution_timestamp)
                  : 'Unresolved / Active'}
              </p>
            </div>

            {/* Duration */}
            <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3.5">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-500 mb-1">
                <Clock className="h-3.5 w-3.5 text-slate-600" />
                <span>Episode Duration</span>
              </div>
              <p className="text-xs font-semibold text-slate-800">
                {formatDuration(
                  evidence.first_detected_timestamp,
                  evidence.resolution_timestamp
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Local Storage Info */}
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/50 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 mb-2">
            <FolderOpen className="h-4 w-4 text-slate-500" />
            <span>Local Storage Path (Auditable Filesystem)</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono text-slate-600">
            <div className="rounded-lg bg-white p-2.5 border border-slate-200">
              <span className="text-slate-400 block text-[10px] uppercase font-sans font-semibold">
                JPEG Image File:
              </span>
              <span className="font-semibold text-slate-800">
                {evidence.image_filename || evidence.evidence_image_filename
                  ? `backend/storage/evidence/${
                      evidence.image_filename || evidence.evidence_image_filename
                    }`
                  : 'No file on disk'}
              </span>
            </div>
            <div className="rounded-lg bg-white p-2.5 border border-slate-200">
              <span className="text-slate-400 block text-[10px] uppercase font-sans font-semibold">
                JSON Metadata Record:
              </span>
              <span className="font-semibold text-slate-800">
                backend/storage/evidence/{evidence.event_id}.json
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-3 border-t border-slate-200/80 bg-slate-50/70 p-4 sm:p-5">
        <button
          onClick={onClose}
          className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
        >
          Close
        </button>
      </div>
    </Dialog>
  );
};

export default IncidentDetailsModal;
