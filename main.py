from fastapi import FastAPI
from asyncio_mqtt import Client
import asyncio
from datetime import datetime
from pydantic import BaseModel
from typing import List
app = FastAPI()

mqqt_client = Client("localhost")

class Device(BaseModel):
    device_id: str
    ip: str
    status: str
    modules: List[str]


connected_devices = {}

@app.get("/")
def read_root():
    return {"Server": "It works!"}

@app.post("/update")
def update_device(device: Device):
    connected_devices[device.device_id] = {
        "ip": device.ip,
        "last_seen": datetime.utcnow()
    }
    return {"status": "ok"}

@app.get("/devices")
def list_devices():
    return connected_devices

@app.on_event("startup")
async def start_mqtt():
    asyncio.create_task(mqtt_listener())

async def mqtt_listener():
    async with mqtt_client as client:
        await client.subscribe("devices/#")
        async with client.unfiltered_messages() as messages:
            async for msg in messages:
                print(f"{msg.topic} -> {msg.payload.decode()}")

@app.post("/command/{device_id}")
async def command(device_id: str, command: str):
    topic = f"devices/{device_id}/cmd"
    await mqtt_client.publish(topic, command.encode())
    return {"sent": command, "to": device_id}
