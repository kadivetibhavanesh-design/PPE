/**
 * Exact schema interfaces matching FastAPI backend responses for monitoring endpoints and WebSockets.
 */

export interface MonitoringStartRequest {
  camera_index?: number;
}

export interface MonitoringStartResponse {
  success: boolean;
  message: string;
  status: string;
  camera_index: number;
  frames_processed: number;
}

export interface MonitoringStopResponse {
  success: boolean;
  message: string;
  status: string;
  frames_processed: number;
}

export interface MonitoringStatusResponse {
  status: 'active' | 'idle' | 'starting' | 'stopping' | 'error';
  is_running: boolean;
  camera_index: number;
  frames_processed: number;
  current_fps: number;
  uptime_seconds: number;
  last_error?: string | null;
  last_exit_reason?: string | null;
  timestamp: number;
  active_workers_count: number;
  compliant_workers_count: number;
  non_compliant_workers_count: number;
  needs_review_workers_count: number;
  active_timers_count: number;
  active_alarms_count: number;
  total_events_count: number;
  active_events_count: number;
  active_model_id?: string;
  active_model_name?: string;
  worker_lifecycle: Record<string, unknown>;
}

export interface MonitoringWorkerItem {
  worker_id?: number;
  worker_track_id: number;
  worker_bounding_box: number[]; // [x1, y1, x2, y2]
  confidence?: number;
  first_seen?: number;
  last_seen?: number;
  total_frames_detected?: number;
  lifecycle_status: string;
  overall_status: 'compliant' | 'non_compliant' | 'needs_review' | string;
  compliance_status?: 'compliant' | 'non_compliant' | 'needs_review' | string;
  overall_reason: string;
  compliant_category_count: number;
  violation_count: number;
  not_detected_count: number;
  uncertain_count: number;
  categories: Record<
    string,
    {
      status?: string;
      confidence?: number;
      box?: number[];
      reason?: string;
      [key: string]: unknown;
    }
  >;
  ppe_status?: Record<string, 'compliant' | 'missing' | 'uncertain' | 'not_detected' | string>;
  missing_ppe?: string[];
  missing_ppe_labels?: string[];
  associated_ppe: Array<{
    class_name?: string;
    ppe_class?: string;
    bbox?: number[];
    ppe_bounding_box?: number[];
    confidence?: number;
    ppe_confidence?: number;
    [key: string]: unknown;
  }>;
}

export interface MonitoringWorkersResponse {
  timestamp: number;
  total_workers: number;
  workers: MonitoringWorkerItem[];
}

export interface ComplianceSummaryResponse {
  timestamp: number;
  total_workers: number;
  compliant_workers: number;
  non_compliant_workers: number;
  needs_review_workers: number;
  workers: MonitoringWorkerItem[];
}

export interface ViolationTimerItem {
  track_id: number;
  category: string;
  elapsed_seconds: number;
  alarm_eligible: boolean;
  start_time: number;
  [key: string]: unknown;
}

export interface ViolationEventItem {
  event_id: string;
  worker_track_id: number;
  ppe_category: string;
  status: 'open' | 'ongoing' | 'resolved' | 'closed';
  severity: 'critical' | 'high' | 'medium' | 'low';
  start_time: number;
  end_time?: number;
  duration_seconds: number;
  [key: string]: unknown;
}

export interface MonitoringSnapshotData {
  timestamp: number;
  frame_width: number;
  frame_height: number;
  detection_count: number;
  worker_lifecycle: Record<string, unknown>;
  total_workers: number;
  total_compliant: number;
  total_non_compliant: number;
  total_needs_review: number;
  workers: MonitoringWorkerItem[];
  unassigned_ppe?: Array<Record<string, unknown>>;
  associations?: Array<Record<string, unknown>>;
  violation_timers: ViolationTimerItem[];
  alarm_eligible_violations?: ViolationTimerItem[];
  active_timer_count: number;
  alarms: Array<Record<string, unknown>>;
  triggered_alarms?: Array<Record<string, unknown>>;
  active_alarms_count: number;
  violation_events: ViolationEventItem[];
  active_violation_events: ViolationEventItem[];
  violation_event_summary?: Record<string, unknown>;
  error?: string | null;
}

export type WebSocketConnectionState = 'Connecting' | 'Connected' | 'Disconnected' | 'Error';

export type WebSocketMessage =
  | {
      type: 'connection_established';
      status: string;
      message: string;
      timestamp: number;
      client_count: number;
    }
  | {
      type: 'monitoring_snapshot';
      timestamp: number;
      data: MonitoringSnapshotData;
    }
  | {
      type: 'monitoring_update';
      timestamp: number;
      data: MonitoringSnapshotData;
    }
  | {
      type: 'pong';
      timestamp: number;
    }
  | {
      type: 'notification';
      timestamp: number;
      data: import('@/types/notification').AppNotification;
    };
