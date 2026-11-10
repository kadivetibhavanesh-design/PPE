/** Types for the Overview dashboard (UI only; demo data until backend integration). */

export type Tone = 'blue' | 'green' | 'amber' | 'red' | 'slate';

export type ViolationSeverity = 'Critical' | 'High' | 'Medium';
export type ViolationStatus = 'Open' | 'Ongoing' | 'Resolved';

export interface DemoViolation {
  eventId: string;
  workerId: number;
  workerName?: string;
  workerRole?: string;
  ppeCategory: string;
  ppeCategories?: string[];
  severity: ViolationSeverity;
  /** Continuous violation duration in seconds. */
  durationSeconds: number;
  status: ViolationStatus;
  time?: string;
  hasEvidence?: boolean;
}

export interface DemoCategoryCount {
  category: string;
  count: number;
}

export interface DemoDistributionSlice {
  name: string;
  value: number;
  tone: Tone;
}

export type ComplianceDistributionSlice = DemoDistributionSlice;
export type DistributionSlice = DemoDistributionSlice;

