/**
 * TypeScript definitions for SafeVision AI incident evidence records.
 */

export type EvidenceSeverity =
  | 'critical'
  | 'high'
  | 'medium'
  | 'low'
  | 'unclassified';

export type EvidenceStatus = 'open' | 'ongoing' | 'resolved' | 'closed';

export interface EvidenceRecord {
  event_id: string;
  worker_track_id: number;
  ppe_category: string;
  severity: EvidenceSeverity | string;
  first_detected_timestamp: number;
  start_timestamp?: number | null;
  evidence_image_filename: string | null;
  image_filename: string | null;
  event_status: EvidenceStatus | string;
  status: EvidenceStatus | string;
  resolution_timestamp: number | null;
  last_updated_timestamp: number;
}

export interface EvidenceListResponse {
  total_count: number;
  evidence: EvidenceRecord[];
}

export interface EvidenceMetrics {
  totalCount: number;
  activeCount: number;
  resolvedCount: number;
  interruptedCount?: number;
  withImageCount: number;
}

