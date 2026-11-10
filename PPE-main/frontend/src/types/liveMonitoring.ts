import type { Tone } from '@/types/overview';

/** Types for the Live Monitoring page (UI only; demo data until backend integration). */

export type ComplianceLabel = 'Compliant' | 'Violation' | 'Needs Review' | 'Not Detected';
export type TrackingStatus = 'Active' | 'Missing' | 'Left';

export interface DemoWorker {
  workerId: number;
  trackingStatus: TrackingStatus;
  compliance: ComplianceLabel;
  /** Continuous violation duration in seconds (0 = none). */
  violationSeconds: number;
}

export interface DemoPpeItem {
  key: string;
  name: string;
  status: ComplianceLabel;
}

export interface DemoDetectionEvent {
  id: string;
  /** Static sample time string, not a real timestamp. */
  time: string;
  workerId: number;
  detection: string;
  /** Confidence in percent. */
  confidence: number;
  status: ComplianceLabel;
}

/** Percent-based box (relative to the preview area) for the illustrative overlay. */
export interface DemoOverlayPerson {
  workerId: number;
  compliant: boolean;
  box: { left: number; top: number; width: number; height: number };
  tags: { text: string; tone: Tone; at: 'head' | 'torso' }[];
}

