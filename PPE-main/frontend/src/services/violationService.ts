import { apiClient } from '@/services/api';

export interface ViolationEvent {
  event_id: string;
  worker_track_id: number;
  ppe_category: string;
  ppe_categories?: string[];
  severity: string;
  status: string;
  start_timestamp: number;
  confirmation_timestamp: number;
  last_updated_timestamp: number;
  violation_duration: number;
  alarm_status: string;
  resolution_timestamp?: number | null;
  closure_timestamp?: number | null;
}

export interface ViolationEventsListResponse {
  total_count: number;
  events: ViolationEvent[];
}

export interface ViolationSummaryResponse {
  timestamp: number;
  total_events_count: number;
  active_events_count: number;
  by_status: Record<string, number>;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
}

export const violationService = {
  /**
   * Retrieves all or filtered violation events from the backend.
   * Endpoint: GET /api/violations
   */
  async getViolations(params?: {
    status?: string;
    severity?: string;
    worker_track_id?: number;
    ppe_category?: string;
    limit?: number;
  }): Promise<ViolationEventsListResponse> {
    const response = await apiClient.get<ViolationEventsListResponse>('/api/violations', {
      params,
    });
    return response.data;
  },

  /**
   * Retrieves all currently active (open/ongoing) violation events.
   * Endpoint: GET /api/violations/active
   */
  async getActiveViolations(): Promise<ViolationEventsListResponse> {
    const response = await apiClient.get<ViolationEventsListResponse>('/api/violations/active');
    return response.data;
  },

  /**
   * Retrieves summary counts of violation events grouped by status, severity, and PPE category.
   * Endpoint: GET /api/violations/summary
   */
  async getSummary(): Promise<ViolationSummaryResponse> {
    const response = await apiClient.get<ViolationSummaryResponse>('/api/violations/summary');
    return response.data;
  },

  /**
   * Marks an active violation event as resolved on the backend.
   * Endpoint: POST /api/violations/{event_id}/resolve
   */
  async resolveViolation(eventId: string): Promise<{ success: boolean; message: string; event?: ViolationEvent }> {
    const response = await apiClient.post<{ success: boolean; message: string; event?: ViolationEvent }>(
      `/api/violations/${encodeURIComponent(eventId)}/resolve`
    );
    return response.data;
  },
};

export default violationService;

