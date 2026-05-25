import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

_connections: list[WebSocket] = []


async def broadcast(event: str, payload: dict[str, Any]) -> None:
    message = json.dumps({"event": event, "data": payload})
    dead: list[WebSocket] = []
    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _connections:
            _connections.remove(ws)


async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    _connections.append(websocket)
    await websocket.send_json({"event": "connected", "data": {"message": "已连接实时推送"}})
    try:
        while True:
            await websocket.receive_text()
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _connections:
            _connections.remove(websocket)
