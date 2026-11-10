import type { MonitoringWorkerItem } from '@/types/monitoring';
import type {
  WorkerItem,
  WorkerComplianceStatus,
  PpeComplianceState,
  PpeCategoryDetail,
  WorkerViolationDetail,
} from '@/types/workers';

export function mapMonitoringWorkerToWorkerItem(w: MonitoringWorkerItem): WorkerItem {
  const compMap: Record<string, WorkerComplianceStatus> = {
    compliant: 'Compliant',
    non_compliant: 'Non-Compliant',
    needs_review: 'Needs Review',
  };

  const ppeStateMap: Record<string, PpeComplianceState> = {
    compliant: 'Compliant',
    missing: 'Missing',
    violation: 'Missing',
    not_detected: 'Not Detected',
    uncertain: 'Uncertain',
  };

  const getCatStatus = (key: string): PpeComplianceState => {
    const raw = (w.ppe_status?.[key] || w.categories?.[key]?.status || 'not_detected').toLowerCase();
    return ppeStateMap[raw] || 'Not Detected';
  };

  const ppeBreakdown: PpeCategoryDetail[] = [
    {
      category: 'Hardhat',
      status: getCatStatus('hardhat'),
      confidence: w.categories?.hardhat?.confidence,
    },
    {
      category: 'Safety Vest',
      status: getCatStatus('safety_vest'),
      confidence: w.categories?.safety_vest?.confidence,
    },
    {
      category: 'Safety Gloves',
      status: getCatStatus('gloves'),
      confidence: w.categories?.gloves?.confidence,
    },
    {
      category: 'Eye Protection',
      status: getCatStatus('goggles'),
      confidence: w.categories?.goggles?.confidence,
    },
    {
      category: 'Protective Mask',
      status: getCatStatus('mask'),
      confidence: w.categories?.mask?.confidence,
    },
    {
      category: 'Safety Footwear',
      status: getCatStatus('safety_shoes'),
      confidence: w.categories?.safety_shoes?.confidence,
    },
  ];

  const missingList = w.missing_ppe_labels && w.missing_ppe_labels.length > 0
    ? w.missing_ppe_labels
    : w.missing_ppe || [];

  const activeViolations: WorkerViolationDetail[] = missingList.map((label, idx) => ({
    violationId: `VIO-W${w.worker_track_id}-${idx + 1}`,
    category: label.replace(/^NO\s+/i, '').replace(/_/g, ' '),
    severity: 'High',
    durationSeconds: 5,
    detectedAt: 'Live in View',
  }));

  return {
    workerId: w.worker_track_id,
    name: `Worker #${w.worker_track_id.toString().padStart(2, '0')}`,
    role: 'Tracked Personnel (ByteTrack)',
    zone: 'Live Camera View',
    firstSeen: 'Current session',
    lastSeen: 'Live in view',
    trackingStatus: w.lifecycle_status === 'active' ? 'Active' : 'Missing',
    complianceStatus: compMap[w.overall_status || w.compliance_status || 'needs_review'] || 'Needs Review',
    activeViolations,
    ppeBreakdown,
    missingPpeLabels: missingList,
    activeIncidentCount: activeViolations.length,
  };
}

