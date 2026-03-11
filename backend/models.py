from datetime import datetime
from typing import List, Any, Dict
from pydantic import BaseModel, Field

class DeviceState(BaseModel):
    """Represents the current state of an IoT device."""
    status: bool = True
    charge_level: int = 0
    actuators: List[str] = Field(default_factory=list)
    emitters: List[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=datetime.now)
    topic: str = ""
    selected: bool = False

    class Config:
        from_attributes = True

class SessionMatrix(BaseModel):
    """Represents the probabilistic connection matrix for the session."""
    devices: List[str] = Field(default_factory=list)
    matrix: List[List[float]] = Field(default_factory=list)

class WebSocketMessage(BaseModel):
    """Standard WebSocket message format."""
    event: str
    data: Dict[str, Any]
