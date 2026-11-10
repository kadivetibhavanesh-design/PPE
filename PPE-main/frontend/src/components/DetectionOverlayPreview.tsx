import React from 'react';
import SectionCard from '@/components/SectionCard';
import type { MonitoringWorkerItem } from '@/types/monitoring';
import { Users, Eye } from 'lucide-react';

interface DetectionOverlayPreviewProps {
  workers: MonitoringWorkerItem[];
  frameWidth?: number;
  frameHeight?: number;
  isRunning: boolean;
}

const LiveWorkerBoundingBox: React.FC<{
  worker: MonitoringWorkerItem;
  frameWidth: number;
  frameHeight: number;
}> = ({ worker, frameWidth, frameHeight }) => {
  const [x1 = 0, y1 = 0, x2 = 0, y2 = 0] = worker.worker_bounding_box;

  // Convert pixel coordinates to percentage
  const fw = frameWidth > 0 ? frameWidth : 1280;
  const fh = frameHeight > 0 ? frameHeight : 720;

  const left = Math.max(0, Math.min(100, (x1 / fw) * 100));
  const top = Math.max(0, Math.min(100, (y1 / fh) * 100));
  const width = Math.max(5, Math.min(100 - left, ((x2 - x1) / fw) * 100));
  const height = Math.max(5, Math.min(100 - top, ((y2 - y1) / fh) * 100));

  const isCompliant =
    worker.overall_status === 'compliant' || worker.compliance_status === 'compliant';
  const isViolation =
    worker.overall_status === 'non_compliant' ||
    worker.compliance_status === 'non_compliant' ||
    (worker.missing_ppe && worker.missing_ppe.length > 0);

  const borderColor = isCompliant ? '#10b981' : isViolation ? '#ef4444' : '#f59e0b';
  const bgColor = isCompliant
    ? 'rgba(16, 185, 129, 0.08)'
    : isViolation
    ? 'rgba(239, 68, 68, 0.08)'
    : 'rgba(245, 158, 11, 0.08)';

  // 1. Confirmed negative violations (Red)
  const missingChips: Array<{ key: string; label: string; color: string }> = [];
  const missingLabels =
    worker.missing_ppe_labels ||
    (worker.missing_ppe || []).map((m) => `NO ${m.toUpperCase().replace(/_/g, ' ')}`);

  missingLabels.forEach((label) => {
    missingChips.push({
      key: `missing-${label}`,
      label: `MISSING: ${label}`,
      color: '#ef4444',
    });
  });

  // 2. Confirmed positive compliant detections (Green)
  const compliantChips: Array<{ key: string; label: string; color: string }> = [];
  // 3. Uncertain detections (Amber)
  const uncertainChips: Array<{ key: string; label: string; color: string }> = [];

  // Check ppe_status and categories
  const categoriesMap = worker.categories || {};
  const ppeStatusMap = worker.ppe_status || {};

  Object.entries(ppeStatusMap).forEach(([catKey, status]) => {
    const conf = categoriesMap[catKey]?.confidence
      ? ` ${Math.round(Number(categoriesMap[catKey].confidence) * 100)}%`
      : '';
    if (status === 'compliant') {
      compliantChips.push({
        key: `compliant-${catKey}`,
        label: `${catKey.toUpperCase().replace(/_/g, ' ')}${conf}`,
        color: '#10b981',
      });
    } else if (status === 'uncertain') {
      uncertainChips.push({
        key: `uncertain-${catKey}`,
        label: `UNCERTAIN: ${catKey.toUpperCase().replace(/_/g, ' ')}`,
        color: '#f59e0b',
      });
    }
  });

  // Fallback if ppe_status is missing
  if (missingChips.length === 0 && compliantChips.length === 0 && uncertainChips.length === 0) {
    Object.entries(categoriesMap).forEach(([catKey, catVal]) => {
      const conf = catVal?.confidence ? ` ${Math.round(Number(catVal.confidence) * 100)}%` : '';
      const st = (catVal?.status || '').toLowerCase();
      if (st === 'compliant') {
        compliantChips.push({
          key: `comp-${catKey}`,
          label: `${catKey.toUpperCase().replace(/_/g, ' ')}${conf}`,
          color: '#10b981',
        });
      } else if (st === 'missing' || st === 'violation' || st === 'non_compliant' || st === 'violation_detected') {
        missingChips.push({
          key: `miss-${catKey}`,
          label: `MISSING: NO ${catKey.toUpperCase().replace(/_/g, ' ')}`,
          color: '#ef4444',
        });
      } else if (st === 'uncertain' || st === 'needs_review') {
        uncertainChips.push({
          key: `unc-${catKey}`,
          label: `UNCERTAIN: ${catKey.toUpperCase().replace(/_/g, ' ')}`,
          color: '#f59e0b',
        });
      }
    });
  }

  const hasAnyDetections = missingChips.length > 0 || compliantChips.length > 0 || uncertainChips.length > 0;

  return (
    <div
      className="absolute rounded border-2 transition-all duration-200"
      style={{
        left: `${left}%`,
        top: `${top}%`,
        width: `${width}%`,
        height: `${height}%`,
        borderColor: borderColor,
        backgroundColor: bgColor,
      }}
    >
      {/* Worker Track ID & Compliance Status Header Tag */}
      <span
        className="absolute -top-5 left-[-2px] whitespace-nowrap rounded-t px-1.5 py-0.5 text-[10px] font-bold text-white shadow-xs"
        style={{ backgroundColor: borderColor }}
      >
        Track #{worker.worker_track_id} · {isViolation ? 'NON-COMPLIANT' : isCompliant ? 'COMPLIANT' : 'REVIEW'}
      </span>

      {/* PPE Category Status Pills inside bounding box */}
      <div className="absolute bottom-1 left-1 right-1 flex flex-col gap-1">
        {/* Negative / Missing PPE Violations (Red) */}
        {missingChips.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {missingChips.map((item) => (
              <span
                key={item.key}
                className="rounded px-1 text-[9px] font-bold leading-tight text-white shadow-xs bg-red-600"
              >
                {item.label}
              </span>
            ))}
          </div>
        )}

        {/* Positive / Compliant PPE (Green) */}
        {compliantChips.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {compliantChips.map((item) => (
              <span
                key={item.key}
                className="rounded px-1 text-[9px] font-bold leading-tight text-white shadow-xs bg-emerald-600"
              >
                {item.label}
              </span>
            ))}
          </div>
        )}

        {/* Uncertain PPE (Amber) */}
        {uncertainChips.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {uncertainChips.map((item) => (
              <span
                key={item.key}
                className="rounded px-1 text-[9px] font-bold leading-tight text-white shadow-xs bg-amber-500"
              >
                {item.label}
              </span>
            ))}
          </div>
        )}

        {/* Undetected fallback badge if completely empty */}
        {!hasAnyDetections && (
          <span className="rounded bg-slate-700/80 px-1 text-[9px] font-medium leading-tight text-slate-200 w-fit">
            NO PPE DETECTED
          </span>
        )}
      </div>
    </div>
  );
};

export const DetectionOverlayPreview: React.FC<DetectionOverlayPreviewProps> = React.memo(({
  workers,
  frameWidth = 1280,
  frameHeight = 720,
  isRunning,
}) => {
  return (
    <SectionCard
      title="Detection Overlay Preview"
      subtitle={
        isRunning
          ? `${workers.length} active worker track${workers.length === 1 ? '' : 's'} mapped in real-time`
          : 'Awaiting video feed stream'
      }
    >
      <div
        className="relative aspect-video w-full overflow-hidden rounded-xl border border-slate-200 bg-slate-950 text-white shadow-inner"
        role="img"
        aria-label="Real-time bounding boxes from YOLO and ByteTrack"
      >
        {/* Subtle grid lines for telemetry spatial context */}
        <div
          className="absolute inset-0 opacity-10 pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />

        {isRunning && workers.length > 0 ? (
          // Real live worker bounding boxes
          workers.map((worker) => (
            <LiveWorkerBoundingBox
              key={worker.worker_track_id}
              worker={worker}
              frameWidth={frameWidth}
              frameHeight={frameHeight}
            />
          ))
        ) : isRunning ? (
          // Running but 0 workers in frame
          <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center text-slate-400">
            <Users className="h-8 w-8 text-slate-600 animate-pulse" />
            <p className="mt-2 text-xs font-semibold text-slate-300">
              Camera monitoring active · No workers currently in frame
            </p>
            <p className="text-[11px] text-slate-500">
              When a person enters the camera field-of-view, detection tracking boxes will render automatically.
            </p>
          </div>
        ) : (
          // Inactive / Idle state
          <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center text-slate-500">
            <Eye className="h-8 w-8 text-slate-600" />
            <p className="mt-2 text-xs font-semibold text-slate-400">
              Monitoring is currently idle
            </p>
            <p className="text-[11px] text-slate-500">
              Click &quot;Start Monitoring&quot; on the Camera Panel to begin real-time worker tracking.
            </p>
          </div>
        )}

        {/* Telemetry Footer */}
        <div className="absolute top-2.5 right-2.5">
          <span className="rounded-md bg-black/60 backdrop-blur-xs px-2 py-1 text-[10px] font-mono font-medium text-slate-300 border border-white/10">
            Resolution: {frameWidth} &times; {frameHeight}
          </span>
        </div>
      </div>
    </SectionCard>
  );
});

export default DetectionOverlayPreview;
