import { apiClient } from '@/services/api';
import type { ModelListResponse, ModelSelectResponse } from '@/types/models';

export const modelService = {
  /**
   * Fetches the catalog of registered YOLO detection models and active state.
   * Endpoint: GET /api/models
   */
  async getModels(): Promise<ModelListResponse> {
    const response = await apiClient.get<ModelListResponse>('/api/models');
    return response.data;
  },

  /**
   * Fetches metadata for the currently active detection model.
   * Endpoint: GET /api/models/active
   */
  async getActiveModel(): Promise<Record<string, unknown>> {
    const response = await apiClient.get<Record<string, unknown>>('/api/models/active');
    return response.data;
  },

  /**
   * Switches the active detection model.
   * Fails with 409 Conflict if camera monitoring is running.
   * Endpoint: POST /api/models/select
   */
  async selectModel(modelId: string): Promise<ModelSelectResponse> {
    const response = await apiClient.post<ModelSelectResponse>('/api/models/select', {
      model_id: modelId,
    });
    return response.data;
  },
};

export default modelService;

