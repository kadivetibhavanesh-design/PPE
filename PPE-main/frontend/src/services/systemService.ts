import { apiClient } from '@/services/api';
import type { SystemHealthResponse, SystemInfoResponse } from '@/types/system';

/**
 * Service to interact with FastAPI system and health monitoring endpoints.
 */
export const systemService = {
  /**
   * Fetches the operational health status of the backend.
   * Endpoint: GET /api/health
   */
  async getHealth(): Promise<SystemHealthResponse> {
    const response = await apiClient.get<SystemHealthResponse>('/api/health');
    return response.data;
  },

  /**
   * Fetches detailed runtime environment metrics and YOLOv8 metadata.
   * Endpoint: GET /api/system/info
   */
  async getSystemInfo(): Promise<SystemInfoResponse> {
    const response = await apiClient.get<SystemInfoResponse>('/api/system/info');
    return response.data;
  },
};

export default systemService;

