import type { PPEStandardCategory } from '@/types/compliance';

/**
 * Types for the Industrial Violations Page (UI only; demo data until backend integration).
 */

export type ViolationSeverityLevel = 'Critical' | 'High' | 'Medium';
export type ViolationLifecycleStatus = 'Open' | 'Ongoing' | 'Resolved' | 'Closed';

export interface ViolationRecord {
  violationId: string;
  workerId: number;
  workerName: string;
  workerRole: string;
  workerZone: string;
  ppeCategory: PPEStandardCategory;
  ppeCategories?: string[];
  severity: ViolationSeverityLevel;
  firstDetected: string;
  confirmationTime?: string;
  resolutionTime?: string;
  durationSeconds: number;
  status: ViolationLifecycleStatus;
  description: string;
  hasEvidence?: boolean;
  firstDetectedTimestamp?: number;
  confirmationTimestamp?: number;
  resolutionTimestamp?: number;
}

export interface ViolationFilterState {
  searchQuery: string;
  ppeCategory: 'All' | PPEStandardCategory;
  severity: 'All' | ViolationSeverityLevel;
  status: 'All' | ViolationLifecycleStatus;
}

export interface ViolationSummaryMetrics {
  totalViolations: number;
  activeViolations: number;
  criticalViolations: number;
  resolvedViolations: number;
}

