import { API_BASE_URL } from '@/services/api';
import type {
  WebSocketConnectionState,
  WebSocketMessage,
} from '@/types/monitoring';

export type MessageListener = (message: WebSocketMessage) => void;
export type StateListener = (state: WebSocketConnectionState) => void;

function resolveWebSocketUrl(): string {
  if (import.meta.env.VITE_WS_BASE_URL) {
    return import.meta.env.VITE_WS_BASE_URL;
  }
  // Convert http://127.0.0.1:8000 to ws://127.0.0.1:8000/ws/monitoring
  const base = API_BASE_URL.replace(/^http/i, 'ws');
  return `${base.replace(/\/+$/, '')}/ws/monitoring`;
}

class WebSocketService {
  private socket: WebSocket | null = null;
  private state: WebSocketConnectionState = 'Disconnected';
  private messageListeners = new Set<MessageListener>();
  private stateListeners = new Set<StateListener>();
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = 5;
  private reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private pingIntervalId: ReturnType<typeof setInterval> | null = null;
  private explicitlyDisconnected = false;

  public getState(): WebSocketConnectionState {
    return this.state;
  }

  private setState(newState: WebSocketConnectionState): void {
    if (this.state !== newState) {
      this.state = newState;
      this.stateListeners.forEach((listener) => {
        try {
          listener(newState);
        } catch (err) {
          console.warn('[WebSocket] Error in state listener:', err);
        }
      });
    }
  }

  /**
   * Initiates a WebSocket connection to /ws/monitoring.
   * Idempotent: does not create duplicate connections if already open or connecting.
   */
  public connect(): void {
    this.explicitlyDisconnected = false;

    // Prevent duplicate connections
    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }

    const url = resolveWebSocketUrl();
    this.setState('Connecting');

    try {
      this.socket = new WebSocket(url);
    } catch (err) {
      console.warn('[WebSocket] Construction failed:', err);
      this.setState('Error');
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      // Note: transition to Connected happens after onopen or connection_established
      this.setState('Connected');
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data) as WebSocketMessage;

        if (parsed.type === 'connection_established') {
          this.setState('Connected');
        }

        // Dispatch to all message listeners
        this.messageListeners.forEach((listener) => {
          try {
            listener(parsed);
          } catch (err) {
            console.warn('[WebSocket] Error in message listener:', err);
          }
        });
      } catch (err) {
        console.warn('[WebSocket] Failed to parse message payload:', err);
      }
    };

    this.socket.onerror = (event: Event) => {
      console.warn('[WebSocket] Socket encountered error:', event);
      this.setState('Error');
    };

    this.socket.onclose = () => {
      this.stopHeartbeat();
      this.socket = null;

      if (!this.explicitlyDisconnected) {
        this.setState('Disconnected');
        this.scheduleReconnect();
      } else {
        this.setState('Disconnected');
      }
    };
  }

  /**
   * Safely disconnects the socket and cancels any pending reconnection attempts.
   */
  public disconnect(): void {
    this.explicitlyDisconnected = true;
    this.reconnectAttempts = 0;

    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }

    this.stopHeartbeat();

    if (this.socket) {
      try {
        this.socket.close(1000, 'Client disconnected');
      } catch (err) {
        console.warn('[WebSocket] Error closing socket:', err);
      }
      this.socket = null;
    }

    this.setState('Disconnected');
  }

  /**
   * Subscribes to incoming parsed WebSocket messages. Returns an unsubscribe function.
   */
  public onMessage(listener: MessageListener): () => void {
    this.messageListeners.add(listener);
    return () => {
      this.messageListeners.delete(listener);
    };
  }

  /**
   * Subscribes to connection state changes. Returns an unsubscribe function.
   */
  public onStateChange(listener: StateListener): () => void {
    this.stateListeners.add(listener);
    // Immediately notify with current state
    listener(this.state);
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  /**
   * Sends a ping action to the backend heartbeat loop.
   */
  public ping(): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(JSON.stringify({ action: 'ping' }));
      } catch (err) {
        console.warn('[WebSocket] Ping send failed:', err);
      }
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingIntervalId = setInterval(() => {
      this.ping();
    }, 25000); // 25s ping keeps connection alive
  }

  private stopHeartbeat(): void {
    if (this.pingIntervalId) {
      clearInterval(this.pingIntervalId);
      this.pingIntervalId = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.explicitlyDisconnected) return;

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn(
        `[WebSocket] Max reconnect attempts (${this.maxReconnectAttempts}) reached. Stopping.`
      );
      this.setState('Disconnected');
      return;
    }

    this.reconnectAttempts += 1;
    // Exponential backoff: 1s, 2s, 4s, 8s, 16s
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 16000);

    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectTimeoutId = null;
      if (!this.explicitlyDisconnected) {
        this.connect();
      }
    }, delay);
  }
}

export const websocketService = new WebSocketService();
export default websocketService;

