# app.py
from fastapi import FastAPI, HTTPException
from asyncio_mqtt import Client, MqttError
import asyncio
from pydantic import BaseModel, Field, RootModel
from typing import Dict, Any
import json

# --- Data Models (Pydantic) ---

class Device(BaseModel):
    device_id: str
    ip: str
    status: str
    is_working: bool = Field(
        default=False,
    )

class WidgetCommandPayload(BaseModel):
    widget_name: str
    widget_num: int
    state: Any  # Can be 0/1, 0-255, a string, etc.

class ListOfWidgetCommandPayload(RootModel[list[WidgetCommandPayload]]):
    pass
class DeviceCommand(BaseModel):
    src_device_id: str
    dst_device_id: str
    cmd: ListOfWidgetCommandPayload

# --- Application and State Initialization ---

app = FastAPI()

# Dictionary to store the state of connected devices
# Key = device_id, Value = Device object
connected_devices: Dict[str, Device] = {}

# --- MQTT Listener (Runs in the background) ---

async def mqtt_listener():
    """Listens for messages from devices (status and acknowledgments)."""
    # Make sure the MQTT broker is running on localhost:1883
    async with Client(
        hostname="localhost",
        port=1883,
        username="server", # <--- Dodaj nazwę użytkownika
        password="server123"  # <--- Dodaj hasło
    ) as client:

        await client.subscribe("devices/+/status") # status check
        await client.subscribe("devices/+/data") # getting data and responses
        
        print("MQTT Listener started and listening on topics 'devices/+/status' and 'devices/+/data'...")
        
        async with client.unfiltered_messages() as messages:
            async for msg in messages:
                try:
                    payload_str = msg.payload.decode()
                    topic_parts = msg.topic.split("/")
                    
                    if len(topic_parts) != 3:
                        continue

                    device_id = topic_parts[1]
                    topic_type = topic_parts[2] # "status" or "data"

                    # 1. Handle STATUS messages
                    if topic_type == "status" :
                        existing_device = connected_devices.get(device_id)
                        if not existing_device:
                            data = json.loads(payload_str)
                            # Preserve is_working state if device reconnects
                            is_working_state = connected_devices.get(device_id, Device(device_id=device_id, ip="", status="")).is_working
                            connected_devices[device_id] = Device(
                                device_id=device_id,
                                ip=data.get("ip", "unknown"),
                                status=data.get("status", "online"),
                                is_working=is_working_state
                            )
                            print(f"Received STATUS from {device_id}: {payload_str}")
                        else:
                            print(f"Selected device is already taken")

                    # 2. Handle DATA messages (including acknowledgments)
                    elif topic_type == "data":
                        data = json.loads(payload_str)
                        # Check if this is an acknowledgment of command execution
                        if data.get("cmd_status") == "done":
                            if device_id in connected_devices:
                                connected_devices[device_id].is_working = False
                                print(f"Device {device_id} has finished its task. Lock released.")
                        else:
                            # Handle other data (e.g., sensor readings)
                            print(f"Received SENSOR DATA from {device_id}: {payload_str}")

                except Exception as e:
                    print(f"Error in MQTT listener: {e} | Topic: {msg.topic} | Payload: {msg.payload.decode()}")

@app.on_event("startup")
async def startup_event():
    """Starts the MQTT listener when the server starts."""
    asyncio.create_task(mqtt_listener())

# --- HTTP API Endpoints ---

@app.get("/")
def read_root():
    return {"Server": "It works!", "MQTT_Status": "Listener running"}

@app.get("/devices")
def list_devices() -> Dict[str, Device]:
    """Returns a dictionary of all devices that have reported their status."""
    return connected_devices

@app.post("/devices/cmd")
async def send_command(command: DeviceCommand):
    """
    Endpoint for sending commands. The server validates if the target
    device is available and not busy.
    """
    dst_id = command.dst_device_id
    
    # 1. Validation: Is the target device connected?
    if dst_id not in connected_devices:
        raise HTTPException(status_code=404, detail=f"Target device '{dst_id}' is not connected.")
        
    target_device = connected_devices[dst_id]
    
    # 2. Validation: Is the target device free?
    if target_device.is_working:
        raise HTTPException(status_code=409, detail=f"Device '{dst_id}' is busy (is_working=true).")
    
    # 3. Action: Lock the device and send the MQTT command
    try:
        target_device.is_working = True
        
        topic = f"devices/{dst_id}/cmd"

        payload = command.cmd.model_dump_json()
        
        async with Client("localhost") as client:
            await client.publish(topic, payload.encode("utf-8"))
        
        print(f"Sent command to {dst_id} on topic '{topic}' | Payload: {payload}")
        
        return {
            "status": "ok",
            "message": "Command sent, device temporarily locked.",
            "target": dst_id
        }
    except Exception as e:
        # In case of an error, release the lock
        target_device.is_working = False
        raise HTTPException(status_code=500, detail=f"Error while sending MQTT message: {e}")