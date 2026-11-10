import { apiClient } from '@/services/api';
import type {
  MonitoringStartRequest,
  MonitoringStartResponse,
  MonitoringStopResponse,
  MonitoringStatusResponse,
  MonitoringWorkersResponse,
  ComplianceSummaryResponse,
} from '@/types/monitoring';

export const monitoringService = {
  /**
   * Starts live webcam capture and YOLO PPE compliance detection.
   * Endpoint: POST /api/monitoring/start
   */
  async startMonitoring(cameraIndex = 0): Promise<MonitoringStartResponse> {
    const payload: MonitoringStartRequest = { camera_index: cameraIndex };
    const response = await apiClient.post<MonitoringStartResponse>(
      '/api/monitoring/start',
      payload,
      { timeout: 20000 } // Dedicated 20s timeout specifically for camera hardware acquisition
    );
    return response.data;
  },

  /**
   * Stops live webcam capture and releases the camera device handle.
   * Endpoint: POST /api/monitoring/stop
   */
  async stopMonitoring(): Promise<MonitoringStopResponse> {
    const response = await apiClient.post<MonitoringStopResponse>(
      '/api/monitoring/stop'
    );
    return response.data;
  },

  /**
   * Retrieves high-level statistics and operational state of the monitoring session.
   * Endpoint: GET /api/monitoring/status
   */
  async getStatus(): Promise<MonitoringStatusResponse> {
    const response = await apiClient.get<MonitoringStatusResponse>(
      '/api/monitoring/status'
    );
    return response.data;
  },

  /**
   * Retrieves active workers detected and tracked in the latest processed frame.
   * Endpoint: GET /api/monitoring/workers
   */
  async getWorkers(): Promise<MonitoringWorkersResponse> {
    const response = await apiClient.get<MonitoringWorkersResponse>(
      '/api/monitoring/workers'
    );
    return response.data;
  },

  /**
   * Retrieves worker PPE compliance evaluations and category breakdowns.
   * Endpoint: GET /api/monitoring/compliance
   */
  async getComplianceSummary(): Promise<ComplianceSummaryResponse> {
    const response = await apiClient.get<ComplianceSummaryResponse>(
      '/api/monitoring/compliance'
    );
    return response.data;
  },
};

export default monitoringService;

