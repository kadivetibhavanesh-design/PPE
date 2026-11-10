/**
 * Exact schema interfaces matching FastAPI backend responses from /api/health and /api/system/info.
 */

export interface SystemHealthResponse {
  status: string; // "healthy"
  application: string; // e.g. "PPE Monitoring System"
  python_version: string;
  pytorch_version: string;
  device: string;
}

export interface SystemInfoResponse {
  status: string; // "online"
  application: string;
  version: string;
  python_version: string;
  pytorch_version: string;
  device: string;
  os: string;
  model: {
    classes?: Record<string, string>;
    num_classes?: number;
    error?: string;
    [key: string]: unknown;
  };
}

export type BackendConnectionState = 'Checking' | 'Connected' | 'Disconnected';

