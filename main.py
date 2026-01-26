import asyncio
import json
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Set

import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# --- Globalne zmienne stanu ---
device_data: Dict[str, Dict[str, Any]] = {}
selected_devices: Set[str] = set()
session_active: bool = False
session_matrix: List[List[float]] = []
session_devices: List[str] = []
active_session_connections: Dict[str, List[str]] = {}
mqtt_client: mqtt.Client = None
main_event_loop = None


# --- Menedżer połączeń WebSocket ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()

# --- Logika MQTT ---


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe("+/status")
    client.subscribe("+/sensor")
    print("Subscribed to +/status and +/sensor topics")


def on_message(client, userdata, msg):
    try:
        topic_parts = msg.topic.split("/")
        device_id = topic_parts[0]
        topic_type = topic_parts[1]
        payload = json.loads(msg.payload.decode())

        if topic_type == "status":
            device_status = payload.get("status", True)
            charge_level = payload.get("charge_level", 0)
            actuators = payload.get("actuators", [])
            emitters = payload.get("emitters", [])

            if device_id not in device_data:
                selected_devices.add(device_id)

            device_data[device_id] = {
                "status": device_status,
                "charge_level": charge_level,
                "last_updated": datetime.now().isoformat(),
                "topic": msg.topic,
                "selected": device_id in selected_devices,
                "actuators": actuators,
                "emitters": emitters,
            }

            if main_event_loop and manager.active_connections:
                message = {
                    "event": "device_update",
                    "data": {"device_id": device_id, "data": device_data[device_id]},
                }
                asyncio.run_coroutine_threadsafe(
                    manager.broadcast(message), main_event_loop
                )

        elif topic_type == "sensor" and session_active:
            sensor_value = payload.get("sensor_value")
            if sensor_value is None:
                return

            try:
                device_index = session_devices.index(device_id)
            except ValueError:
                return  # Device not in the current session

            if sensor_value == 0:  # Button pressed
                print(f"Device {device_id} pressed. Evaluating connections...")
                active_session_connections[device_id] = []
                device_row = session_matrix[device_index]

                for target_index, prob in enumerate(device_row):
                    if random.random() < prob:
                        target_device_id = session_devices[target_index]
                        print(
                            f"  Connecting {device_id} -> {target_device_id} (prob: {prob:.2f})"
                        )
                        publish_command(target_device_id, {"state": True})
                        active_session_connections[device_id].append(target_device_id)

            elif sensor_value == 1:  # Button released
                if device_id in active_session_connections:
                    print(f"Device {device_id} released. Deactivating connections...")
                    for target_device_id in active_session_connections[device_id]:
                        print(f"  Disconnecting {device_id} -> {target_device_id}")
                        publish_command(target_device_id, {"state": False})
                    del active_session_connections[device_id]

    except json.JSONDecodeError:
        print(f"Failed to decode JSON from topic {msg.topic}: {msg.payload}")
    except Exception as e:
        print(f"Error processing message: {e}")


def publish_command(device_id: str, payload: Dict[str, Any]):
    """Publikuje komendę do urządzenia przez MQTT"""
    if mqtt_client is None:
        print(f"MQTT client not initialized, cannot send command to {device_id}")
        return False

    try:
        topic = f"{device_id}/command"
        payload_str = json.dumps(payload)

        result = mqtt_client.publish(topic, payload_str)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Published command to {topic}: {payload_str}")
            return True
        else:
            print(f"Failed to publish command to {topic}, rc={result.rc}")
            return False
    except Exception as e:
        print(f"Error publishing command to {device_id}: {e}")
        return False


def init_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        mqtt_host = os.getenv("MQTT_HOST", "localhost")
        mqtt_client.connect(mqtt_host, 1883, 60)
        mqtt_client.loop_start()
        print(f"MQTT client started, connected to {mqtt_host}")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")


# --- Zadania w tle (Cleanup) ---


async def cleanup_old_devices_task():
    print("Starting cleanup task...")
    while True:
        try:
            current_time = datetime.now()
            devices_to_remove = []

            for device_id, data in list(device_data.items()):
                last_updated = datetime.fromisoformat(data["last_updated"])
                if (current_time - last_updated).total_seconds() > 300:
                    devices_to_remove.append(device_id)

            for device_id in devices_to_remove:
                del device_data[device_id]
                await manager.broadcast(
                    {"event": "device_removed", "data": {"device_id": device_id}}
                )
                print(f"Removed inactive device: {device_id}")

        except Exception as e:
            print(f"Error in cleanup task: {e}")

        await asyncio.sleep(60)


# --- Konfiguracja FastAPI Lifecycle ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_event_loop
    main_event_loop = asyncio.get_running_loop()

    init_mqtt()
    cleanup_task = asyncio.create_task(cleanup_old_devices_task())

    yield

    if mqtt_client:
        mqtt_client.loop_stop()
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

# --- Endpointy HTTP (API) ---


@app.get("/api/devices")
async def get_devices():
    return JSONResponse(device_data)


@app.get("/api/selected-devices")
async def get_selected_devices():
    return JSONResponse(list(selected_devices))


# --- Endpoint WebSocket ---


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global session_active

    await manager.connect(websocket)
    client_id = websocket.client.host
    print(f"Client connected: {client_id}")

    try:
        await websocket.send_json(
            {
                "event": "connection_confirmed",
                "data": {
                    "status": "connected",
                    "server_time": datetime.now().isoformat(),
                },
            }
        )
        await websocket.send_json({"event": "devices_data", "data": device_data})

        await websocket.send_json(
            {
                "event": "session_status",
                "data": {"active": session_active, "action": "status_check"},
            }
        )

        while True:
            data = await websocket.receive_json()
            event_type = data.get("event")
            payload = data.get("data", {})

            if event_type == "device_selected":
                device_id = payload.get("device_id")
                is_selected = payload.get("selected", False)

                if is_selected:
                    selected_devices.add(device_id)
                else:
                    selected_devices.discard(device_id)

                if device_id in device_data:
                    device_data[device_id]["selected"] = is_selected

                print(
                    f"Device {device_id} {'selected' if is_selected else 'deselected'}"
                )

            elif event_type == "device_status_change":
                device_id = payload.get("device_id")
                new_status = payload.get("status", True)

                device_data[device_id]["status"] = new_status
                success = publish_command(
                    device_id, {"state": new_status}
                )

                if success:
                    print(
                        f"Sent status command to {device_id}: {'ON' if new_status else 'OFF'}"
                    )
                else:
                    print(f"Failed to send status command to {device_id}")

            elif event_type == "start_session":
                session_matrix.clear()
                session_devices.clear()
                active_session_connections.clear()

                devices_in_session = list(selected_devices)
                if not devices_in_session:
                    print("No devices selected for the session.")
                    continue

                session_active = True
                session_devices.extend(devices_in_session)

                n = len(session_devices)
                session_matrix.clear()
                
                if n > 0:
                    for i in range(n):
                        # Initialize row with low random probabilities
                        row = [0.0 if r == i else random.uniform(0, 0.3) for r in range(n)]
                        
                        if n > 1:
                            # Pick a random target distinct from self to be deterministic
                            target = random.choice([x for x in range(n) if x != i])
                            row[target] = 1.0
                        
                        session_matrix.append(row)

                print("Session started with connection matrix.")
                print("Devices:", session_devices)
                print("Matrix:", session_matrix)

                await manager.broadcast(
                    {
                        "event": "session_status",
                        "data": {"active": True, "action": "started"},
                    }
                )
                await manager.broadcast(
                    {
                        "event": "session_matrix_update",
                        "data": {
                            "devices": session_devices,
                            "matrix": session_matrix,
                        },
                    }
                )

            elif event_type == "stop_session":
                session_active = False
                session_matrix.clear()
                session_devices.clear()
                active_session_connections.clear()
                print("Session stopped")
                await manager.broadcast(
                    {
                        "event": "session_status",
                        "data": {"active": False, "action": "stopped"},
                    }
                )
                await manager.broadcast(
                    {
                        "event": "session_matrix_update",
                        "data": {"devices": [], "matrix": []},
                    }
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Client disconnected: {client_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    print("Starting FastAPI API server...")
    uvicorn.run(app, host="0.0.0.0", port=5000)
