import axios, { AxiosError } from 'axios';

/**
 * Base URL for the FastAPI backend API.
 * Configured via VITE_API_BASE_URL with fallback to http://127.0.0.1:8000.
 */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 8000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor ensuring all internal API requests are prefixed with /api
apiClient.interceptors.request.use((config) => {
  if (config.url && !config.url.startsWith('/api') && !config.url.startsWith('http')) {
    config.url = `/api${config.url.startsWith('/') ? '' : '/'}${config.url}`;
  }
  return config;
});

// Response interceptor for consistent error inspection
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      // Server returned a response outside 2xx
      console.warn(`[API] HTTP ${error.response.status}:`, error.response.data || error.message);
    } else if (error.request) {
      // Network failure or backend server offline
      console.warn('[API] Network error: No response received from backend at', API_BASE_URL);
    } else {
      console.warn('[API] Request configuration error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default apiClient;
