/**
 * Common Types for the AI-Powered Industrial PPE Monitoring System
 */

export type PPECategory =
  | 'hardhat'
  | 'safety_vest'
  | 'safety_glasses'
  | 'gloves'
  | 'safety_boots'
  | 'mask';

export type ComplianceStatus = 'compliant' | 'non_compliant' | 'needs_review';

export type WorkerLifecycleState = 'active' | 'missing' | 'left';

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface WorkerSummary {
  worker_track_id: number;
  overall_status: ComplianceStatus;
  bbox?: [number, number, number, number];
  compliant_categories?: string[];
  violated_categories?: string[];
  uncertain_categories?: string[];
  continuous_violation_seconds?: number;
  lifecycle_state?: WorkerLifecycleState;
}

export interface ViolationEvent {
  event_id: string;
  worker_track_id: number;
  ppe_category: PPECategory | string;
  status: 'open' | 'ongoing' | 'resolved' | 'closed';
  severity: 'critical' | 'high' | 'medium' | 'low';
  start_time: number;
  end_time?: number;
  duration_seconds: number;
}

export interface AlarmItem {
  worker_track_id: number;
  ppe_category: string;
  alarm_eligible: boolean;
  active: boolean;
  timestamp: number;
}

export interface SystemInfo {
  status: string;
  python_version?: string;
  pytorch_version?: string;
  device?: string;
  model_name?: string;
  yolo_loaded?: boolean;
}

export interface MonitoringStatus {
  status: 'idle' | 'active' | 'stopping' | 'error';
  is_running: boolean;
  camera_index: number;
  frames_processed: number;
  current_fps: number;
  uptime_seconds: number;
  last_error?: string | null;
  active_workers_count: number;
  compliant_workers_count: number;
  non_compliant_workers_count: number;
  needs_review_workers_count: number;
  active_timers_count: number;
  active_alarms_count: number;
}

export * from './workers';
export * from './compliance';
export * from './violations';
export * from './system';
export * from './monitoring';
export * from './evidence';
export * from './email';
export * from './settings';

