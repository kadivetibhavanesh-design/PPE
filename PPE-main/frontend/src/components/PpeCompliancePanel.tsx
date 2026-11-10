import React from 'react';
import { HardHat, Shirt, Hand, Glasses, ScanFace, Footprints, ShieldCheck, AlertTriangle, CheckCircle2 } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import StatusPill from '@/components/StatusPill';
import SectionCard from '@/components/SectionCard';
import type { MonitoringWorkerItem } from '@/types/monitoring';

interface PpeCompliancePanelProps {
  workers: MonitoringWorkerItem[];
  selectedWorkerId: number | null;
  onSelectWorker: (id: number) => void;
}

const PPE_STANDARDS: Array<{ key: string; label: string; icon: LucideIcon }> = [
  { key: 'hardhat', label: 'Hardhat', icon: HardHat },
  { key: 'safety_vest', label: 'Safety Vest', icon: Shirt },
  { key: 'gloves', label: 'Gloves', icon: Hand },
  { key: 'goggles', label: 'Goggles', icon: Glasses },
  { key: 'mask', label: 'Mask', icon: ScanFace },
  { key: 'safety_shoes', label: 'Safety Shoes', icon: Footprints },
];

export const PpeCompliancePanel: React.FC<PpeCompliancePanelProps> = React.memo(({
  workers,
  selectedWorkerId,
  onSelectWorker,
}) => {
  // Select user-picked worker, or worker with active violation, or first detected worker
  const activeWorker =
    (selectedWorkerId !== null ? workers.find((w) => w.worker_track_id === selectedWorkerId) : null) ||
    workers.find(
      (w) =>
        w.overall_status === 'non_compliant' ||
        w.compliance_status === 'non_compliant' ||
        (w.missing_ppe && w.missing_ppe.length > 0)
    ) ||
    workers[0] ||
    null;

  if (activeWorker) {
    console.debug(
      `[PpeCompliancePanel] Worker #${activeWorker.worker_track_id}:`,
      `overall=${activeWorker.overall_status}`,
      `ppe_status=`,
      activeWorker.ppe_status,
      `missing=`,
      activeWorker.missing_ppe_labels
    );
  }

  const missingLabels = activeWorker?.missing_ppe_labels || (activeWorker?.missing_ppe || []).map(
    (m) => `NO ${m.toUpperCase().replace(/_/g, ' ')}`
  );
  const isNonCompliant =
    activeWorker?.overall_status === 'non_compliant' ||
    activeWorker?.compliance_status === 'non_compliant' ||
    (missingLabels && missingLabels.length > 0);
  const isCompliant =
    (activeWorker?.overall_status === 'compliant' ||
      activeWorker?.compliance_status === 'compliant') &&
    !isNonCompliant;

  return (
    <SectionCard
      title="Live PPE Compliance"
      subtitle={
        activeWorker
          ? `Evaluating Worker #${activeWorker.worker_track_id.toString().padStart(2, '0')}`
          : 'Awaiting worker detection'
      }
    >
      {workers.length > 1 && (
        <div className="mb-3 flex items-center gap-2 overflow-x-auto pb-1 text-xs">
          <span className="text-slate-500 font-medium">Select worker:</span>
          {workers.map((w) => {
            const hasViolations =
              w.overall_status === 'non_compliant' ||
              w.compliance_status === 'non_compliant' ||
              (w.missing_ppe && w.missing_ppe.length > 0);
            return (
              <button
                key={w.worker_track_id}
                type="button"
                onClick={() => onSelectWorker(w.worker_track_id)}
                className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-semibold transition ${
                  activeWorker?.worker_track_id === w.worker_track_id
                    ? 'bg-brand-600 text-white shadow-xs'
                    : hasViolations
                    ? 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                <span>#{w.worker_track_id}</span>
                {hasViolations && (
                  <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse" />
                )}
              </button>
            );
          })}
        </div>
      )}

      {activeWorker ? (
        <div className="space-y-2.5">
          {/* Prominent Violation or Compliance Status Banner */}
          {isNonCompliant && (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50/90 p-2.5 text-xs text-red-800 shadow-2xs">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 mt-0.5" />
              <div>
                <p className="font-semibold text-red-900">
                  VIOLATION: {missingLabels && missingLabels.length > 0 ? missingLabels.join(', ') : 'Missing Required PPE'}
                </p>
                <p className="text-[11px] text-red-700 mt-0.5">
                  Worker #{activeWorker.worker_track_id} is non-compliant. Continuous violation timer active.
                </p>
              </div>
            </div>
          )}

          {isCompliant && (
            <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50/90 p-2.5 text-xs text-emerald-800 shadow-2xs">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
              <p className="font-semibold text-emerald-900">
                Worker #{activeWorker.worker_track_id} is COMPLIANT with required PPE standards.
              </p>
            </div>
          )}

          <ul className="grid grid-cols-1 gap-2">
            {PPE_STANDARDS.map(({ key, label, icon: Icon }) => {
              // Read from ppe_status dictionary first (with key aliases), then fallback to categories object
              const ppeStatusDirect =
                activeWorker.ppe_status?.[key] ||
                activeWorker.ppe_status?.[key.replace('_', ' ')] ||
                activeWorker.ppe_status?.[key.replace(' ', '_')];
              const cat =
                activeWorker.categories?.[key] ||
                activeWorker.categories?.[key.replace('_', ' ')] ||
                activeWorker.categories?.[key.replace(' ', '_')];
              const rawStatus = (ppeStatusDirect || cat?.status || '').toLowerCase().trim();
              const conf = cat?.confidence ? Math.round(Number(cat.confidence) * 100) : null;

              let tone: 'green' | 'red' | 'amber' | 'slate' = 'slate';
              let statusLabel = 'Not Detected';

              if (rawStatus === 'compliant') {
                if (key === 'mask') {
                  // Pretrained model has no positive mask class; never falsely verify mask compliance
                  tone = 'slate';
                  statusLabel = 'Not Detected';
                } else {
                  tone = 'green';
                  statusLabel = conf ? `Compliant (${conf}%)` : 'Compliant';
                }
              } else if (
                rawStatus === 'missing' ||
                rawStatus === 'violation' ||
                rawStatus === 'non_compliant' ||
                rawStatus === 'violation_detected'
              ) {
                tone = 'red';
                statusLabel = conf ? `Missing (${conf}%)` : 'Missing';
              } else if (rawStatus === 'uncertain' || rawStatus === 'needs_review') {
                tone = 'amber';
                statusLabel = 'Uncertain';
              } else if (rawStatus === 'unsupported') {
                tone = 'slate';
                statusLabel = 'Unsupported';
              } else {
                tone = 'slate';
                statusLabel = 'Not Detected';
              }

              return (
                <li
                  key={key}
                  className={`flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5 shadow-2xs transition-colors ${
                    tone === 'red'
                      ? 'border-red-200 bg-red-50/40'
                      : tone === 'green'
                      ? 'border-emerald-200/80 bg-emerald-50/30'
                      : 'border-slate-200/80 bg-white/80'
                  }`}
                >
                  <span className="flex items-center gap-2.5 text-xs font-semibold text-slate-800">
                    <Icon className={`h-4 w-4 ${tone === 'red' ? 'text-red-500' : tone === 'green' ? 'text-emerald-500' : 'text-slate-500'}`} />
                    {label}
                  </span>
                  <StatusPill tone={tone}>{statusLabel}</StatusPill>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500">
          <ShieldCheck className="h-8 w-8 text-slate-400" />
          <p className="mt-2 text-xs font-semibold text-slate-700">
            No active worker evaluated
          </p>
          <p className="text-[11px] text-slate-400">
            Start monitoring and position a worker in camera view to evaluate PPE compliance.
          </p>
        </div>
      )}
    </SectionCard>
  );
});

export default PpeCompliancePanel;
