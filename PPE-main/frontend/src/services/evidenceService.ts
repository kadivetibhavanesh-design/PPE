import { apiClient, API_BASE_URL } from '@/services/api';
import type { EvidenceListResponse, EvidenceRecord } from '@/types/evidence';

export const evidenceService = {
  /**
   * Fetches all recorded incident evidence records from the backend with optional query filters.
   * Endpoint: GET /api/evidence
   */
  async getEvidenceList(params?: {
    worker_track_id?: number;
    ppe_category?: string;
    status?: string;
  }): Promise<EvidenceRecord[]> {
    const response = await apiClient.get<EvidenceListResponse>('/api/evidence', {
      params,
    });
    return response.data?.evidence || [];
  },

  /**
   * Fetches detailed evidence metadata for a specific incident event ID.
   * Endpoint: GET /api/evidence/{event_id}
   */
  async getEvidenceById(eventId: string): Promise<EvidenceRecord> {
    const response = await apiClient.get<EvidenceRecord>(
      `/api/evidence/${encodeURIComponent(eventId)}`
    );
    return response.data;
  },

  /**
   * Constructs the URL for the captured evidence JPEG image.
   * Endpoint: GET /api/evidence/{event_id}/image
   */
  getEvidenceImageUrl(eventId: string): string {
    return `${API_BASE_URL}/api/evidence/${encodeURIComponent(eventId)}/image`;
  },

  /**
   * Constructs the URL for the captured evidence image by filename.
   * Endpoint: GET /api/evidence/file/{filename}
   */
  getEvidenceFileUrl(filename: string): string {
    return `${API_BASE_URL}/api/evidence/file/${encodeURIComponent(filename)}`;
  },
};

export default evidenceService;

