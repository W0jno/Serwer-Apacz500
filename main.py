from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
app = FastAPI()

class Device(BaseModel):
    device_id: str
    ip: str

connected_devices = {}

@app.get("/")
def read_root():
    return {"Hello": "World"}

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

