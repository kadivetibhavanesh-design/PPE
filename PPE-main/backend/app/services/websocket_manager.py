import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("ppe_monitoring.websocket_manager")


class ConnectionManager:
    """
    Manages active WebSocket connections for live PPE monitoring broadcasts.
    Provides robust multi-client tracking, error-resilient broadcasting,
    non-blocking execution, and safe removal of disconnected clients.
    """

    def __init__(self) -> None:
        # Map: WebSocket -> associated event loop
        self._active_connections: Dict[WebSocket, Optional[asyncio.AbstractEventLoop]] = {}
        # Cache of the last broadcast payload to prevent duplicate stale broadcasts
        self._last_broadcast_timestamp: Optional[float] = None

    async def connect(self, websocket: WebSocket) -> None:
        """
        Accepts and registers a new WebSocket client connection.

        Args:
            websocket: The incoming FastAPI WebSocket connection.
        """
        await websocket.accept()
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        self._active_connections[websocket] = loop
        logger.info(
            f"WebSocket client connected. Active connections: {len(self._active_connections)}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Safely unregisters a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
        """
        if websocket in self._active_connections:
            del self._active_connections[websocket]
            logger.info(
                f"WebSocket client disconnected. Remaining connections: {len(self._active_connections)}"
            )

    def get_connected_count(self) -> int:
        """Returns the number of currently connected clients."""
        return len(self._active_connections)

    def has_connections(self) -> bool:
        """Returns True if there is at least one active client connection."""
        return len(self._active_connections) > 0

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> bool:
        """
        Sends a JSON message to a single specific client connection.

        Returns:
            bool: True if sent successfully, False if failed/disconnected.
        """
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.debug(f"Failed to send personal message to WebSocket client: {e}")
            self.disconnect(websocket)
            return False

    async def broadcast(self, message: Dict[str, Any]) -> int:
        """
        Broadcasts a JSON message asynchronously to all active WebSocket clients.
        Automatically isolates and removes any client that fails or disconnects.

        Args:
            message: JSON-serializable dictionary to broadcast.

        Returns:
            int: Number of successfully notified clients.
        """
        if not self._active_connections:
            return 0

        disconnected_clients: List[WebSocket] = []
        success_count = 0

        try:
            curr_loop = asyncio.get_running_loop()
        except RuntimeError:
            curr_loop = None

        # Iterate over connections snapshot
        for client, loop in list(self._active_connections.items()):
            try:
                if loop is None or loop == curr_loop:
                    await client.send_json(message)
                elif loop.is_running():
                    fut = asyncio.run_coroutine_threadsafe(client.send_json(message), loop)
                    await asyncio.wrap_future(fut)
                else:
                    disconnected_clients.append(client)
                    continue
                success_count += 1
            except (WebSocketDisconnect, RuntimeError, Exception) as exc:
                logger.debug(f"Error broadcasting to client, marking for removal: {exc}")
                disconnected_clients.append(client)

        # Cleanup failed connections
        for dead_client in disconnected_clients:
            self.disconnect(dead_client)

        return success_count

    def broadcast_sync(self, message: Dict[str, Any]) -> int:
        """
        Thread-safe synchronous bridge for broadcasting to WebSockets
        from synchronous video processing or detection pipelines.

        Args:
            message: JSON-serializable dictionary to broadcast.

        Returns:
            int: Number of active connections targeted.
        """
        if not self.has_connections():
            return 0

        try:
            curr_loop = asyncio.get_running_loop()
        except RuntimeError:
            curr_loop = None

        if curr_loop is not None and curr_loop.is_running():
            curr_loop.create_task(self.broadcast(message))
            return len(self._active_connections)

        # Called from outside an active loop (e.g. sync thread or unit test)
        disconnected: List[WebSocket] = []
        success_count = 0
        scheduled_loops: Set[asyncio.AbstractEventLoop] = set()

        for ws, loop in list(self._active_connections.items()):
            try:
                if loop is not None and loop.is_running():
                    # Non-blocking async dispatch on event loop without stalling detection thread
                    if loop not in scheduled_loops:
                        asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)
                        scheduled_loops.add(loop)
                    success_count += 1
                elif loop is None:
                    # No loop attached (e.g. mock socket in unit tests); execute synchronously
                    asyncio.run(ws.send_json(message))
                    success_count += 1
                else:
                    disconnected.append(ws)
            except Exception as e:
                logger.debug(f"Sync broadcast error on socket: {e}")
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

        return success_count

    def broadcast_monitoring_update(self, monitoring_payload: Dict[str, Any]) -> int:
        """
        Convenience method to wrap and broadcast monitoring payload with timestamp and type metadata.
        Guards against duplicate stale payloads using timestamp checks.

        Args:
            monitoring_payload: Monitoring frame payload dictionary.

        Returns:
            int: Number of target clients.
        """
        if not self.has_connections() or not isinstance(monitoring_payload, dict):
            return 0

        payload_ts = monitoring_payload.get("timestamp")
        if payload_ts is not None and payload_ts == self._last_broadcast_timestamp:
            # Skip duplicate stale snapshot
            return 0

        self._last_broadcast_timestamp = payload_ts

        message = {
            "type": "monitoring_update",
            "timestamp": payload_ts if payload_ts is not None else time.time(),
            "data": monitoring_payload,
        }

        return self.broadcast_sync(message)

    def clear(self) -> None:
        """Clears all active connections (used during session reset or testing)."""
        count = len(self._active_connections)
        self._active_connections.clear()
        self._last_broadcast_timestamp = None
        logger.info(f"Cleared all {count} WebSocket connections.")


# Shared module singleton instance
_manager_instance: Optional[ConnectionManager] = None


def get_websocket_manager() -> ConnectionManager:
    """Returns the shared ConnectionManager singleton."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ConnectionManager()
    return _manager_instance
