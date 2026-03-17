from datetime import datetime
from typing import List, Any, Dict, Literal
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


class DependencyRule(BaseModel):
    """Server-side widget dependency rule (source event -> target MQTT publish)."""

    id: str
    source_device_id: str
    source_emitter: str = "default"
    trigger_state: Literal["on", "off", "any"] = "on"
    target_device_id: str
    target_topic: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class DependencyRuleCreate(BaseModel):
    """Payload used to create a dependency rule."""

    source_device_id: str
    source_emitter: str = "default"
    trigger_state: Literal["on", "off", "any"] = "on"
    target_device_id: str
    target_topic: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
