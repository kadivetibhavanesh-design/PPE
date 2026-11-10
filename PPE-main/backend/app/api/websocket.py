import json
import logging
import time
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import get_monitoring_service
from app.services.ppe_monitoring_service import PPEMonitoringService
from app.services.websocket_manager import ConnectionManager, get_websocket_manager

logger = logging.getLogger("ppe_monitoring.api.websocket")

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/monitoring")
async def websocket_monitoring_endpoint(
    websocket: WebSocket,
    monitoring_service: PPEMonitoringService = Depends(get_monitoring_service),
    manager: ConnectionManager = Depends(get_websocket_manager),
):
    """
    WebSocket endpoint broadcasting real-time PPE detection, tracking,
    violation timers, alarms, and event updates to connected clients.
    """
    # 1. Accept and register connection
    await manager.connect(websocket)

    try:
        # 2. Send initial connection confirmation
        connect_ack = {
            "type": "connection_established",
            "status": "connected",
            "message": "Connected to real-time PPE monitoring stream",
            "timestamp": time.time(),
            "client_count": manager.get_connected_count(),
        }
        await websocket.send_json(connect_ack)

        # 3. Send latest available monitoring snapshot
        try:
            snapshot = monitoring_service.get_latest_monitoring_data()
            if snapshot is not None:
                snapshot_msg = {
                    "type": "monitoring_snapshot",
                    "timestamp": snapshot.get("timestamp", time.time()),
                    "data": snapshot,
                }
                await websocket.send_json(snapshot_msg)
        except Exception as snap_err:
            logger.warning(f"Failed to send initial monitoring snapshot: {snap_err}")

        # 4. Event loop listening for client heartbeat / messages or disconnect
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
                if data.get("action") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time(),
                    })
            except Exception:
                # Handle non-JSON or plain text heartbeats
                if text.strip().lower() == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time(),
                    })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client cleanly disconnected from /ws/monitoring")
    except Exception as e:
        manager.disconnect(websocket)
        logger.debug(f"Client disconnected with exception from /ws/monitoring: {e}")

