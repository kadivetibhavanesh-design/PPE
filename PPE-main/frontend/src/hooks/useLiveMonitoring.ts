import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { monitoringService } from '@/services/monitoringService';
import { websocketService } from '@/services/websocketService';
import type {
  MonitoringStatusResponse,
  MonitoringSnapshotData,
  MonitoringWorkerItem,
  ViolationTimerItem,
  ViolationEventItem,
  WebSocketConnectionState,
  WebSocketMessage,
} from '@/types/monitoring';

export interface UseLiveMonitoringReturn {
  status: MonitoringStatusResponse | null;
  isStarting: boolean;
  isStopping: boolean;
  isLoadingStatus: boolean;
  wsState: WebSocketConnectionState;
  latestSnapshot: MonitoringSnapshotData | null;
  workers: MonitoringWorkerItem[];
  activeViolations: ViolationEventItem[];
  violationTimers: ViolationTimerItem[];
  error: string | null;
  startMonitoring: (cameraIndex?: number) => Promise<boolean>;
  stopMonitoring: () => Promise<boolean>;
  refreshStatus: () => Promise<void>;
  reconnectWebSocket: () => void;
  clearError: () => void;
}

export function useLiveMonitoring(): UseLiveMonitoringReturn {
  const [status, setStatus] = useState<MonitoringStatusResponse | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [wsState, setWsState] = useState<WebSocketConnectionState>(
    websocketService.getState()
  );
  const [latestSnapshot, setLatestSnapshot] = useState<MonitoringSnapshotData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isMountedRef = useRef(true);

  // Fetch REST status
  const refreshStatus = useCallback(async () => {
    try {
      const data = await monitoringService.getStatus();
      if (isMountedRef.current) {
        setStatus(data);
      }
    } catch (err: unknown) {
      if (isMountedRef.current) {
        console.warn('[Monitoring] Failed to fetch monitoring status:', err);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoadingStatus(false);
      }
    }
  }, []);

  // Handle incoming WebSocket messages
  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    if (!isMountedRef.current) return;

    if (message.type === 'monitoring_snapshot' || message.type === 'monitoring_update') {
      const snap = message.data;
      setLatestSnapshot(snap);

      // Keep status in sync with streaming frame metrics without redundant re-renders
      setStatus((prev) => {
        if (!prev) return prev;

        const totalEvents =
          typeof snap.violation_event_summary?.total_events_count === 'number'
            ? snap.violation_event_summary.total_events_count
            : prev.total_events_count;
        const activeEvents = snap.active_violation_events?.length ?? prev.active_events_count;

        // Skip re-render if high-level status metrics have not meaningfully changed
        if (
          prev.is_running === true &&
          prev.status === 'active' &&
          prev.active_workers_count === snap.total_workers &&
          prev.compliant_workers_count === snap.total_compliant &&
          prev.non_compliant_workers_count === snap.total_non_compliant &&
          prev.needs_review_workers_count === snap.total_needs_review &&
          prev.active_timers_count === snap.active_timer_count &&
          prev.active_alarms_count === snap.active_alarms_count &&
          prev.total_events_count === totalEvents &&
          prev.active_events_count === activeEvents
        ) {
          return prev;
        }

        return {
          ...prev,
          status: 'active',
          is_running: true,
          active_workers_count: snap.total_workers,
          compliant_workers_count: snap.total_compliant,
          non_compliant_workers_count: snap.total_non_compliant,
          needs_review_workers_count: snap.total_needs_review,
          active_timers_count: snap.active_timer_count,
          active_alarms_count: snap.active_alarms_count,
          total_events_count: totalEvents,
          active_events_count: activeEvents,
        };
      });
    }
  }, []);

  // Initialize REST status and WebSocket connection on mount
  useEffect(() => {
    isMountedRef.current = true;

    // 1. Initial REST status probe
    monitoringService
      .getStatus()
      .then((data) => {
        if (isMountedRef.current) {
          setStatus(data);
        }
      })
      .catch((err: unknown) => {
        if (isMountedRef.current) {
          console.warn('[Monitoring] Failed to fetch initial status:', err);
        }
      })
      .finally(() => {
        if (isMountedRef.current) {
          setIsLoadingStatus(false);
        }
      });

    // 2. Subscribe to WebSocket state and message stream
    const unsubscribeState = websocketService.onStateChange((state) => {
      if (isMountedRef.current) {
        setWsState(state);
      }
    });

    const unsubscribeMsg = websocketService.onMessage(handleWebSocketMessage);

    // 3. Connect to WebSocket
    websocketService.connect();

    // Poll status periodically (every 5 seconds) as fallback sync
    const pollInterval = setInterval(() => {
      refreshStatus();
    }, 5000);

    return () => {
      isMountedRef.current = false;
      clearInterval(pollInterval);
      unsubscribeState();
      unsubscribeMsg();
      // We keep socket managed or close on page leave
    };
  }, [refreshStatus, handleWebSocketMessage]);

  // Start monitoring action
  const startMonitoring = useCallback(
    async (cameraIndex = 0): Promise<boolean> => {
      setIsStarting(true);
      setError(null);
      try {
        const result = await monitoringService.startMonitoring(cameraIndex);
        if (result.success) {
          // Immediately sync status
          await refreshStatus();
          return true;
        } else {
          setError(result.message || 'Failed to start camera monitoring');
          return false;
        }
      } catch (err: unknown) {
        let msg = 'Failed to start camera monitoring';
        if (err && typeof err === 'object' && 'response' in err) {
          const resp = (err as { response?: { data?: { detail?: string } } }).response;
          if (resp?.data?.detail) {
            msg = resp.data.detail;
          }
        } else if (err instanceof Error) {
          msg = err.message;
        }
        setError(msg);
        return false;
      } finally {
        if (isMountedRef.current) {
          setIsStarting(false);
        }
      }
    },
    [refreshStatus]
  );

  // Stop monitoring action
  const stopMonitoring = useCallback(async (): Promise<boolean> => {
    setIsStopping(true);
    setError(null);
    try {
      const result = await monitoringService.stopMonitoring();
      if (result.success) {
        await refreshStatus();
        return true;
      } else {
        setError(result.message || 'Failed to stop monitoring');
        return false;
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to stop monitoring';
      setError(msg);
      return false;
    } finally {
      if (isMountedRef.current) {
        setIsStopping(false);
      }
    }
  }, [refreshStatus]);

  const reconnectWebSocket = useCallback(() => {
    websocketService.disconnect();
    websocketService.connect();
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Memoized derived collections to avoid creating new array instances on unrelated re-renders
  const workers = useMemo(() => latestSnapshot?.workers ?? [], [latestSnapshot?.workers]);
  const activeViolations = useMemo(
    () => latestSnapshot?.active_violation_events ?? [],
    [latestSnapshot?.active_violation_events]
  );
  const violationTimers = useMemo(
    () => latestSnapshot?.violation_timers ?? [],
    [latestSnapshot?.violation_timers]
  );

  return {
    status,
    isStarting,
    isStopping,
    isLoadingStatus,
    wsState,
    latestSnapshot,
    workers,
    activeViolations,
    violationTimers,
    error,
    startMonitoring,
    stopMonitoring,
    refreshStatus,
    reconnectWebSocket,
    clearError,
  };
}

export default useLiveMonitoring;
