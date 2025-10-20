from fastapi import FastAPI, HTTPException, Query
from asyncio_mqtt import Client, MqttError
import asyncio
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

mqtt_client = Client("localhost", port=1883)

class Device(BaseModel):
    device_id: str
    ip: str
    status: str
    is_working: bool

class DeviceCommand(BaseModel):
    src_device_id: str
    dst_device_id: str
    cmd: str

# Słownik urządzeń podłączonych, klucz = device_id
connected_devices: Dict[str, Device] = {}

@app.get("/")
def read_root():
    return {"Server": "It works!"}

@app.get("/devices")
def list_devices():
    return connected_devices

@app.on_event("startup")
async def startup_event():
    # Uruchom listener MQTT
    asyncio.create_task(mqtt_listener())

async def mqtt_listener():
    while True:
        async with mqtt_client as client:
            # Subskrybujemy wszystkie wiadomości od urządzeń
            await client.subscribe("devices/+/status")
            async with client.unfiltered_messages() as messages:
                async for msg in messages:
                    payload = msg.payload.decode()
                    topic_parts = msg.topic.split("/")
                    if len(topic_parts) == 3:
                        device_id = topic_parts[1]
                        # Zakładamy, że payload = "ip,status" np. "192.168.1.10,online"
                        try:
                            ip, status = payload.split(",")
                        except ValueError:
                            ip, status = "unknown", "unknown"
                        connected_devices[device_id] = Device(
                            device_id=device_id,
                            ip=ip,
                            status=status,
                            is_working=False
                        )
                    print(f"Updated {device_id}: {payload}")

@app.post("/devices/cmd")
async def chain(command: DeviceCommand):
    topic = f"/devices/{command.dst_device_id}/cmd"

    try:
        if(connected_devices[command.dst_device_id].is_working == False):
            await mqtt_client.publish(topic, command.cmd.encode())
            connected_devices[command.dst_device_id].is_working = True
            return {"status": "ok", "topic": topic, "cmd": command.cmd, "target": command.dst_device_id}
        else:
            return{"status": "error", "detail": "Destination device is busy", "target": command.dst_device_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

