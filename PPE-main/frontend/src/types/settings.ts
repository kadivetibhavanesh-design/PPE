import type { EmailSettings } from './email';

export interface ModelProfileInfo {
  profile_id: string;
  name: string;
  description: string;
  capabilities: string[];
  positive_mask_support: boolean;
  positive_glove_support: boolean;
  recommended_for: string;
  is_active: boolean;
}

export interface SanitizedModelsResponse {
  active_profile_id: string;
  is_monitoring_running: boolean;
  profiles: ModelProfileInfo[];
}

export interface CameraSettings {
  device_index: number;
  resolution: string;
  width: number;
  height: number;
  fps: number;
  backend: string;
}

export interface PPEDetectionSettings {
  global_confidence: number;
  min_ioa: number;
  violation_duration: number;
  violation_cooldown: number;
  enabled_categories: string[];
  category_confidence: Record<string, number>;
}

export interface AlertSettings {
  sound_enabled: boolean;
  visual_enabled: boolean;
  duration_ms: number;
  frequency_hz: number;
  cooldown_seconds: number;
  triggers: Record<string, boolean>;
}

export interface StorageSettings {
  retention_days: number;
  image_capture_enabled: boolean;
}

export interface ApplicationPreferences {
  theme: 'light' | 'dark' | 'system';
  default_page: string;
  refresh_interval_ms: number;
  notification_mode: string;
  datetime_format: string;
  ui_density: string;
}

export interface FullSettings {
  model: {
    selected_profile: string;
  };
  camera: CameraSettings;
  ppe: PPEDetectionSettings;
  alerts: AlertSettings;
  storage: StorageSettings;
  preferences: ApplicationPreferences;
  email?: EmailSettings;
}

export interface CameraTestResult {
  success: boolean;
  available: boolean;
  in_use: boolean;
  message: string;
  resolution?: string;
  fps?: number;
  latency_ms?: number;
}

export interface CameraDeviceItem {
  index: number;
  name: string;
  available: boolean;
  in_use: boolean;
}

export interface SystemMetrics {
  timestamp: number;
  performance_status: 'Normal' | 'Moderate' | 'High' | 'Critical';
  cpu: {
    percent: number;
    physical_cores: number;
    logical_cores: number;
    frequency_mhz: number;
  };
  ram: {
    total_gb: number;
    used_gb: number;
    free_gb: number;
    percent: number;
    backend_process_rss_mb: number;
  };
  gpu: {
    available: boolean;
    name: string;
    vram_total_mb: number;
    vram_used_mb: number;
    vram_percent: number;
    status: string;
  };
  ai_pipeline: {
    model_init_ms: number;
    latest_inference_latency_ms: number;
    avg_inference_latency_ms: number;
    max_inference_latency_ms: number;
    avg_frame_time_ms: number;
    fps: number;
    total_detections: number;
    confidence_threshold: number;
  };
  camera: {
    is_running: boolean;
    camera_index: number;
    fps: number;
    frames_processed: number;
    uptime_seconds: number;
  };
  storage: {
    storage_directory: string;
    total_files: number;
    image_files: number;
    metadata_files: number;
    incident_records_count: number;
    total_size_bytes: number;
    total_size_mb: number;
    disk_total_gb: number;
    disk_used_gb: number;
    disk_free_gb: number;
    image_capture_enabled: boolean;
  };
}

export interface SystemInfoServiceStatus {
  name: string;
  status: string;
  description: string;
}

export interface SystemInfoData {
  application_name: string;
  tagline: string;
  version: string;
  environment: string;
  api_base_url: string;
  python_version: string;
  pytorch_version: string;
  os_platform: string;
  cpu_cores: {
    physical: number;
    logical: number;
  };
  system_uptime_seconds: number;
  services: SystemInfoServiceStatus[];
}

export interface StorageCleanupResult {
  success: boolean;
  removed_count: number;
  expired_incidents: number;
  freed_bytes: number;
  freed_mb: number;
  retention_days: number;
  message?: string;
}

