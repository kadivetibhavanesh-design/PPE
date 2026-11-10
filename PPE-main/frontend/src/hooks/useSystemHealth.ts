import { useState, useEffect, useCallback } from 'react';
import { systemService } from '@/services/systemService';
import type {
  SystemHealthResponse,
  SystemInfoResponse,
  BackendConnectionState,
} from '@/types/system';

export interface UseSystemHealthReturn {
  connectionState: BackendConnectionState;
  healthData: SystemHealthResponse | null;
  systemInfo: SystemInfoResponse | null;
  isLoading: boolean;
  error: string | null;
  lastChecked: Date | null;
  refresh: () => Promise<void>;
}

/**
 * Hook to monitor real backend connectivity via GET /api/health.
 * Automatically checks connection upon mount and exposes a manual refresh function.
 */
export function useSystemHealth(): UseSystemHealthReturn {
  const [connectionState, setConnectionState] = useState<BackendConnectionState>('Checking');
  const [healthData, setHealthData] = useState<SystemHealthResponse | null>(null);
  const [systemInfo, setSystemInfo] = useState<SystemInfoResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const executeCheck = useCallback(async () => {
    setIsLoading(true);
    setConnectionState('Checking');
    setError(null);

    try {
      const data = await systemService.getHealth();
      if (data && data.status === 'healthy') {
        setHealthData(data);
        setConnectionState('Connected');
        setError(null);

        // Optionally fetch detailed system info if health succeeded
        try {
          const info = await systemService.getSystemInfo();
          setSystemInfo(info);
        } catch {
          // Failure to fetch secondary info doesn't revoke healthy connection
        }
      } else {
        setHealthData(null);
        setConnectionState('Disconnected');
        setError('Unexpected backend response status');
      }
    } catch (err: unknown) {
      setHealthData(null);
      setSystemInfo(null);
      setConnectionState('Disconnected');
      const message =
        err instanceof Error ? err.message : 'Failed to connect to backend server';
      setError(message);
    } finally {
      setIsLoading(false);
      setLastChecked(new Date());
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    systemService
      .getHealth()
      .then((data) => {
        if (!isMounted) return;
        if (data && data.status === 'healthy') {
          setHealthData(data);
          setConnectionState('Connected');
          setError(null);

          systemService
            .getSystemInfo()
            .then((info) => {
              if (isMounted) setSystemInfo(info);
            })
            .catch(() => {});
        } else {
          setHealthData(null);
          setConnectionState('Disconnected');
          setError('Unexpected backend response status');
        }
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        setHealthData(null);
        setSystemInfo(null);
        setConnectionState('Disconnected');
        setError(err instanceof Error ? err.message : 'Failed to connect to backend server');
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
          setLastChecked(new Date());
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  return {
    connectionState,
    healthData,
    systemInfo,
    isLoading,
    error,
    lastChecked,
    refresh: executeCheck,
  };
}

export default useSystemHealth;
