import random
from datetime import datetime
from typing import Dict, List, Set

from fastapi import WebSocket
from .models import DeviceState, SessionMatrix, WebSocketMessage

# --- Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: WebSocketMessage):
        # Convert Pydantic model to dict for JSON serialization
        msg_dict = message.model_dump(mode='json')
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(msg_dict)
            except Exception:
                self.disconnect(connection)

# --- Device Manager ---
class DeviceManager:
    def __init__(self):
        self.devices: Dict[str, DeviceState] = {}
        # selected_devices tracks user selection preferences even if device is offline
        self.selected_device_ids: Set[str] = set() 

    def update_device(self, device_id: str, payload: dict, topic: str) -> DeviceState:
        """Updates or registers a device based on MQTT payload."""
        current_time = datetime.now()
        
        # If new device, auto-select if configured? (Currently logic says: "if not in data, add to selected")
        # The original logic was: "if device_id not in device_data: selected_devices.add(device_id)"
        if device_id not in self.devices:
             self.selected_device_ids.add(device_id)

        # Parse payload
        status = payload.get("status", True)
        charge_level = payload.get("charge_level", 0)
        actuators = payload.get("actuators", [])
        emitters = payload.get("emitters", [])

        state = DeviceState(
            status=status,
            charge_level=charge_level,
            actuators=actuators,
            emitters=emitters,
            last_updated=current_time,
            topic=topic,
            selected=(device_id in self.selected_device_ids)
        )
        self.devices[device_id] = state
        return state

    def set_selection(self, device_id: str, selected: bool):
        if selected:
            self.selected_device_ids.add(device_id)
        else:
            self.selected_device_ids.discard(device_id)
        
        if device_id in self.devices:
            self.devices[device_id].selected = selected

    def get_all_devices(self) -> Dict[str, dict]:
        return {k: v.model_dump(mode='json') for k, v in self.devices.items()}

    def get_selected_ids(self) -> List[str]:
        return list(self.selected_device_ids)

    def cleanup_inactive(self, timeout_seconds: int = 300) -> List[str]:
        current_time = datetime.now()
        removed_ids = []
        for device_id, state in list(self.devices.items()):
            if (current_time - state.last_updated).total_seconds() > timeout_seconds:
                del self.devices[device_id]
                removed_ids.append(device_id)
        return removed_ids

# --- Session Manager ---
class SessionManager:
    def __init__(self):
        self.active: bool = False
        self.matrix: SessionMatrix = SessionMatrix()
        # Active connections: source_id -> list of target_ids currently triggered
        self.active_connections: Dict[str, List[str]] = {}
        # Last known emitter state: "<source_id>:<emitter_id>" -> bool
        self.emitter_states: Dict[str, bool] = {}

    def start_session(self, selected_ids: List[str]) -> SessionMatrix:
        self.active = True
        self.active_connections.clear()
        self.emitter_states.clear()
        
        devices = sorted(selected_ids) # Sort for consistency
        n = len(devices)
        matrix_data = []

        if n > 0:
            for i in range(n):
                # Initialize row with low random probabilities
                row = [0.0 if r == i else random.uniform(0, 0.3) for r in range(n)]
                
                if n > 1:
                    # Pick a random target distinct from self to be deterministic (high prob)
                    target = random.choice([x for x in range(n) if x != i])
                    row[target] = 1.0
                
                matrix_data.append(row)
        
        self.matrix = SessionMatrix(devices=devices, matrix=matrix_data)
        return self.matrix

    def stop_session(self):
        self.active = False
        self.matrix = SessionMatrix()
        self.active_connections.clear()
        self.emitter_states.clear()

    def handle_emitter_event(self, source_id: str, emitter_id: str, is_active: bool) -> List[str]:
        """Handles generic emitter state transitions.

        Triggers targets only on state changes:
        - False -> True: activate target connections
        - True -> False: deactivate previously active connections
        """
        key = f"{source_id}:{emitter_id}"
        previous_state = self.emitter_states.get(key)

        # Ignore repeated level samples with unchanged state.
        if previous_state is not None and previous_state == is_active:
            return []

        self.emitter_states[key] = is_active

        if is_active:
            return self.handle_button_press(source_id)
        return self.handle_button_release(source_id)

    def handle_button_press(self, source_id: str) -> List[str]:
        """Returns a list of target device IDs to trigger."""
        if not self.active:
            return []
        
        try:
            device_index = self.matrix.devices.index(source_id)
        except ValueError:
            return [] # Source not in session

        targets_to_trigger = []
        self.active_connections[source_id] = []
        
        row = self.matrix.matrix[device_index]
        for target_index, prob in enumerate(row):
            if random.random() < prob:
                target_id = self.matrix.devices[target_index]
                targets_to_trigger.append(target_id)
                self.active_connections[source_id].append(target_id)
        
        return targets_to_trigger

    def handle_button_release(self, source_id: str) -> List[str]:
        """Returns a list of target device IDs to detune (turn off)."""
        if source_id in self.active_connections:
            targets = self.active_connections[source_id]
            del self.active_connections[source_id]
            return targets
        return []
