import json
import os
import asyncio
from datetime import datetime
from typing import List, Dict, Set, Any
from contextlib import asynccontextmanager

import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# --- Globalne zmienne stanu ---
device_data: Dict[str, Dict[str, Any]] = {}
selected_devices: Set[str] = set()
session_active: bool = False
mqtt_client: mqtt.Client = None
main_event_loop = None  # Uchwyt do pętli zdarzeń, aby wywołać async z wątku MQTT

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
        # Wysyłamy wiadomość do wszystkich podłączonych klientów
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
    print("Subscribed to +/status topics")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        device_id = topic.split("/")[0]
        payload = json.loads(msg.payload.decode())

        device_status = payload.get("status", False)
        charge_level = payload.get("charge_level", 0)

        # Logika dodawania urządzeń
        if device_id not in device_data:
            selected_devices.add(device_id)

        device_data[device_id] = {
            "status": device_status,
            "charge_level": charge_level,
            "last_updated": datetime.now().isoformat(),
            "topic": topic,
            "selected": device_id in selected_devices,
        }

        operational = "operational" if device_status else "not operational"
        print(f"Updated device {device_id}: {operational}, charge={charge_level}%")

        # Emitowanie przez WebSocket (most sync -> async)
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
                await manager.broadcast({
                    "event": "device_removed",
                    "data": {"device_id": device_id}
                })
                print(f"Removed inactive device: {device_id}")
            
        except Exception as e:
            print(f"Error in cleanup task: {e}")
        
        await asyncio.sleep(60)

# --- Konfiguracja FastAPI Lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start-up
    global main_event_loop
    main_event_loop = asyncio.get_running_loop()
    
    init_mqtt()
    cleanup_task = asyncio.create_task(cleanup_old_devices_task())
    
    yield
    
    # Shut-down
    if mqtt_client:
        mqtt_client.loop_stop()
    cleanup_task.cancel()
    print("Shutdown complete")

app = FastAPI(lifespan=lifespan)

# CORS - Bardzo ważne dla Reacta (localhost:5173 -> localhost:5000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # W produkcji warto to ograniczyć do domeny frontendu
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
    # 1. DEKLARACJA GLOBAL NA SAMYM POCZĄTKU
    global session_active 
    
    await manager.connect(websocket)
    client_id = websocket.client.host
    print(f"Client connected: {client_id}")
    
    try:
        # Stan początkowy
        await websocket.send_json({
            "event": "connection_confirmed",
            "data": {"status": "connected", "server_time": datetime.now().isoformat()}
        })
        await websocket.send_json({
            "event": "devices_data",
            "data": device_data
        })
        
        # Odtworzenie stanu sesji dla nowego klienta
        # TERAZ TO ZADZIAŁA, BO 'session_active' JEST JUŻ ZADEKLAROWANE JAKO GLOBAL
        await websocket.send_json({
            "event": "session_status",
            "data": {"active": session_active, "action": "status_check"}
        })

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

                print(f"Device {device_id} {'selected' if is_selected else 'deselected'}")
                
            elif event_type == "start_session":
                # TU USUNELIŚMY 'global session_active', BO JEST JUŻ NA GÓRZE
                session_active = True
                print("Session started")
                await manager.broadcast({
                    "event": "session_status", 
                    "data": {"active": True, "action": "started"}
                })

            elif event_type == "stop_session":
                # TU TEŻ NIE POTRZEBA PONOWNEJ DEKLARACJI
                session_active = False
                print("Session stopped")
                await manager.broadcast({
                    "event": "session_status", 
                    "data": {"active": False, "action": "stopped"}
                })

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