import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- Globalne zmienne stanu ---
device_data: Dict[str, Dict[str, Any]] = {}
selected_devices: Set[str] = set()
session_active: bool = False
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
        topic = msg.topic
        parts = topic.split("/")
        device_id = parts[0]
        subtopic = parts[1] if len(parts) > 1 else ""
        payload = json.loads(msg.payload.decode())

        # Logika dodawania urządzeń
        if device_id not in device_data:
            selected_devices.add(device_id)
            device_data[device_id] = {
                "status": False,
                "charge_level": 0,
                "last_updated": datetime.now().isoformat(),
                "topic": f"{device_id}/status",
                "selected": True,
                "actuators": [],
                "emitters": [],
                "sensors": {}
            }

        if subtopic == "status":
            device_data[device_id].update({
                "status": payload.get("status", False),
                "charge_level": payload.get("charge_level", 0),
                "last_updated": datetime.now().isoformat(),
                "topic": topic,
                "selected": device_id in selected_devices,
                "actuators": payload.get("actuators", []),
                "emitters": payload.get("emitters", [])
            })
        elif subtopic == "sensor":
            device_data[device_id]["sensors"] = payload
            device_data[device_id]["last_updated"] = datetime.now().isoformat()

        # Emitowanie przez WebSocket
        if main_event_loop and manager.active_connections:
            message = {
                "event": "device_update",
                "data": {"device_id": device_id, "data": device_data[device_id]}
            }
            asyncio.run_coroutine_threadsafe(manager.broadcast(message), main_event_loop)

    except json.JSONDecodeError:
        print(f"Failed to decode JSON from topic {msg.topic}: {msg.payload}")
    except Exception as e:
        print(f"Error processing message: {e}")

def publish_device_command(device_id: str, command: str, value: Any):
    """Publikuje komendę do urządzenia przez MQTT"""
    if mqtt_client is None:
        print(f"MQTT client not initialized, cannot send command to {device_id}")
        return False
    
    try:
        topic = f"{device_id}/command"
        payload = json.dumps({
            "command": command,
            "value": value,
            "timestamp": datetime.now().isoformat()
        })
        
        result = mqtt_client.publish(topic, payload)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Published command to {topic}: {command}={value}")
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
                    print(f"Sent status command to {device_id}: {'ON' if new_status else 'OFF'}")
                else:
                    print(f"Failed to send status command to {device_id}")
                
                # Opcjonalnie: możemy zaktualizować lokalny stan
                # ale lepiej poczekać na potwierdzenie z urządzenia przez status topic
                
            elif event_type == "component_command":
                device_id = payload.get("device_id")
                component_type = payload.get("component_type")  # "actuator" or "emitter"
                name = payload.get("name")
                state = payload.get("state", False)

                if device_id and component_type and name:
                    success = publish_device_command(
                        device_id,
                        f"{component_type}",
                        {"name": name, "state": state}
                    )
                    if success:
                        print(f"Sent {component_type} command to {device_id}: {name}={'ON' if state else 'OFF'}")
                    else:
                        print(f"Failed to send {component_type} command to {device_id}")

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