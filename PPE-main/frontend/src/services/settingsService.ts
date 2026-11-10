import apiClient from '@/services/api';
import type {
  FullSettings,
  SanitizedModelsResponse,
  CameraTestResult,
  CameraDeviceItem,
  SystemMetrics,
  SystemInfoData,
  StorageCleanupResult,
} from '@/types/settings';

export const settingsService = {
  /**
   * Retrieves the full persisted system settings across all 8 modules.
   */
  async getAllSettings(): Promise<FullSettings> {
    const res = await apiClient.get<FullSettings>('/api/settings');
    return res.data;
  },

  /**
   * Updates and saves the system configuration.
   */
  async updateSettings(settings: Partial<FullSettings>): Promise<{ success: boolean; settings: FullSettings }> {
    const res = await apiClient.put<{ success: boolean; settings: FullSettings }>('/api/settings', settings);
    return res.data;
  },

  /**
   * Resets all configuration to factory defaults.
   */
  async resetToDefaults(): Promise<{ success: boolean; settings: FullSettings }> {
    const res = await apiClient.post<{ success: boolean; settings: FullSettings }>('/api/settings/reset');
    return res.data;
  },

  /**
   * Retrieves sanitized AI model profiles (never leaks raw repo/weights).
   */
  async getModelProfiles(): Promise<SanitizedModelsResponse> {
    const res = await apiClient.get<SanitizedModelsResponse>('/api/settings/models');
    return res.data;
  },

  /**
   * Activates a selected model profile (guards against monitoring running).
   */
  async activateModelProfile(profileId: string): Promise<{ success: boolean; message: string; active_profile_id: string }> {
    const res = await apiClient.post<{ success: boolean; message: string; active_profile_id: string }>(
      '/api/settings/models/activate',
      { profile_id: profileId }
    );
    return res.data;
  },

  /**
   * Safely tests camera availability by briefly reading 1 frame and releasing.
   */
  async testCamera(deviceIndex: number, backend: string): Promise<CameraTestResult> {
    const res = await apiClient.get<CameraTestResult>('/api/settings/camera/test', {
      params: { device_index: deviceIndex, backend },
    });
    return res.data;
  },

  /**
   * Scans available connected camera hardware.
   */
  async scanCameraDevices(): Promise<CameraDeviceItem[]> {
    const res = await apiClient.get<{ devices: CameraDeviceItem[] }>('/api/settings/camera/devices');
    return res.data.devices;
  },

  /**
   * Triggers test audio alert tone.
   */
  async testAlarmTone(durationMs?: number, frequencyHz?: number): Promise<{ success: boolean; message: string }> {
    const res = await apiClient.post<{ success: boolean; message: string }>('/api/settings/alerts/test', {
      duration_ms: durationMs,
      frequency_hz: frequencyHz,
    });
    return res.data;
  },

  /**
   * Immediately silences and stops all active alarms.
   */
  async stopAllAlarms(): Promise<{ success: boolean; stopped_count: number; message: string }> {
    const res = await apiClient.post<{ success: boolean; stopped_count: number; message: string }>('/api/settings/alerts/stop-all');
    return res.data;
  },

  /**
   * Retrieves real-time hardware and AI pipeline metrics.
   */
  async getSystemMetrics(): Promise<SystemMetrics> {
    const res = await apiClient.get<SystemMetrics>('/api/settings/system/metrics');
    return res.data;
  },

  /**
   * Cleans up expired incident evidence older than the retention threshold.
   */
  async cleanupEvidence(retentionDays?: number): Promise<StorageCleanupResult> {
    const res = await apiClient.post<StorageCleanupResult>('/api/settings/storage/cleanup', {
      retention_days: retentionDays,
    });
    return res.data;
  },

  /**
   * Retrieves application system architecture and service status metadata.
   */
  async getSystemInfo(): Promise<SystemInfoData> {
    const res = await apiClient.get<SystemInfoData>('/api/settings/system/info');
    return res.data;
  },
};
