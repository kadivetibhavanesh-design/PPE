/**
 * Types for the Workers Management page (UI only; demo data until backend integration).
 */

export type WorkerTrackingStatus = 'Active' | 'Missing' | 'Left';
export type WorkerComplianceStatus = 'Compliant' | 'Non-Compliant' | 'Needs Review';
export type PpeComplianceState = 'Compliant' | 'Non-Compliant' | 'Missing' | 'Uncertain' | 'Not Detected' | 'Not Verifiable';

export type PpeCategoryName =
  | 'Hardhat'
  | 'Safety Vest'
  | 'Safety Gloves'
  | 'Eye Protection'
  | 'Protective Mask'
  | 'Safety Footwear';

export interface PpeCategoryDetail {
  category: PpeCategoryName;
  status: PpeComplianceState;
  confidence?: number;
  notes?: string;
}

export interface WorkerViolationDetail {
  violationId: string;
  category: string;
  severity: 'Critical' | 'High' | 'Medium';
  durationSeconds: number;
  detectedAt: string;
}

export interface WorkerItem {
  workerId: number;
  name: string;
  role: string;
  zone: string;
  firstSeen: string;
  lastSeen: string;
  trackingStatus: WorkerTrackingStatus;
  complianceStatus: WorkerComplianceStatus;
  activeViolations: WorkerViolationDetail[];
  ppeBreakdown: PpeCategoryDetail[];
  missingPpeLabels?: string[];
  activeIncidentCount?: number;
  firstSeenTimestamp?: number;
  lastSeenTimestamp?: number;
}

export interface WorkerFilterState {
  searchQuery: string;
  trackingStatus: 'All' | WorkerTrackingStatus;
  complianceStatus: 'All' | WorkerComplianceStatus;
}

export interface WorkerSummaryMetrics {
  totalWorkers: number;
  activeWorkers: number;
  missingWorkers: number;
  workersWithViolations: number;
}
