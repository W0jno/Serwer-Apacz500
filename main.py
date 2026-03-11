import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.managers import DeviceManager, SessionManager, ConnectionManager
from backend.mqtt_service import MQTTService
from backend.models import WebSocketMessage

# --- Initialization ---
device_manager = DeviceManager()
session_manager = SessionManager()
connection_manager = ConnectionManager()

# Pass managers to MQTT Service
mqtt_service = MQTTService(device_manager, session_manager, connection_manager)

# --- Background Tasks ---
async def cleanup_old_devices_task():
    print("Starting cleanup task...")
    while True:
        try:
            removed_ids = device_manager.cleanup_inactive(timeout_seconds=300)
            
            for device_id in removed_ids:
                print(f"Removed inactive device: {device_id}")
                await connection_manager.broadcast(
                    WebSocketMessage(
                        event="device_removed",
                        data={"device_id": device_id}
                    )
                )
        except Exception as e:
            print(f"Error in cleanup task: {e}")

        await asyncio.sleep(60)

# --- FastAPI Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_service.start()
    cleanup_task = asyncio.create_task(cleanup_old_devices_task())

    yield

    mqtt_service.stop()
    cleanup_task.cancel()
    print("Shutdown complete")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HTTP Endpoints ---

@app.get("/api/devices")
async def get_devices():
    return JSONResponse(device_manager.get_all_devices())

@app.get("/api/selected-devices")
async def get_selected_devices():
    return JSONResponse(device_manager.get_selected_ids())

# --- WebSocket Endpoint ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await connection_manager.connect(websocket)
    client_id = websocket.client.host if websocket.client else "unknown"
    print(f"Client connected: {client_id}")

    try:
        # Prune inactive devices (older than 30s) on connection to ensure fresh view
        removed_ids = device_manager.cleanup_inactive(timeout_seconds=30)
        for device_id in removed_ids:
            print(f"Removed inactive device (refresh cleanup): {device_id}")
            await connection_manager.broadcast(
                WebSocketMessage(
                    event="device_removed",
                    data={"device_id": device_id}
                )
            )

        # Initial State Sync
        await websocket.send_json({
            "event": "connection_confirmed",
            "data": {
                "status": "connected",
                "server_time": datetime.now().isoformat(),
            },
        })
        
        # Send current devices
        await websocket.send_json({
            "event": "devices_data",
            "data": device_manager.get_all_devices()
        })

        # Send session status
        await websocket.send_json({
            "event": "session_status",
            "data": {"active": session_manager.active, "action": "status_check"},
        })
        
        # If session active, send matrix
        if session_manager.active:
             await websocket.send_json({
                "event": "session_matrix_update",
                "data": session_manager.matrix.model_dump(mode='json'),
            })

        # Command Loop
        while True:
            data = await websocket.receive_json()
            event_type = data.get("event")
            payload = data.get("data", {})

            if event_type == "device_selected":
                device_id = payload.get("device_id")
                is_selected = payload.get("selected", False)
                
                device_manager.set_selection(device_id, is_selected)
                print(f"Device {device_id} {'selected' if is_selected else 'deselected'}")

            elif event_type == "device_status_change":
                device_id = payload.get("device_id")
                new_status = payload.get("status", True)
                
                success = mqtt_service.publish_command(device_id, {"state": new_status})
                if success and device_id in device_manager.devices:
                    device_manager.devices[device_id].status = new_status
                    print(f"Sent status command to {device_id}: {'ON' if new_status else 'OFF'} (Optimistic update)")

            elif event_type == "device_command":
                device_id = payload.get("device_id")
                actuator = payload.get("actuator", "default")
                value = payload.get("value")

                command_payload = {
                    "actuator": actuator,
                    "value": value,
                }

                success = mqtt_service.publish_command(device_id, command_payload)
                if success:
                    print(f"Sent generic command to {device_id}: actuator={actuator}, value={value}")

            elif event_type == "start_session":
                selected_ids = device_manager.get_selected_ids()
                if not selected_ids:
                    print("No devices selected for session.")
                    continue
                
                matrix = session_manager.start_session(selected_ids)
                print("Session started.")
                print("Matrix:", matrix.model_dump(mode='json'))

                await connection_manager.broadcast(
                    WebSocketMessage(
                        event="session_status",
                        data={"active": True, "action": "started"}
                    )
                )
                await connection_manager.broadcast(
                    WebSocketMessage(
                        event="session_matrix_update",
                        data=matrix.model_dump(mode='json')
                    )
                )

            elif event_type == "stop_session":
                session_manager.stop_session()
                print("Session stopped")
                
                await connection_manager.broadcast(
                    WebSocketMessage(
                        event="session_status",
                        data={"active": False, "action": "stopped"}
                    )
                )
                await connection_manager.broadcast(
                    WebSocketMessage(
                        event="session_matrix_update",
                        data={"devices": [], "matrix": []}
                    )
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        print(f"Client disconnected: {client_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI API server...")
    uvicorn.run(app, host="0.0.0.0", port=5000)