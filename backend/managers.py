import random
import uuid
from datetime import datetime
from typing import Dict, List, Set

from fastapi import WebSocket

from .models import DependencyRule, DependencyRuleCreate, DeviceState, SessionMatrix, WebSocketMessage


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

        if device_id not in self.devices:
            self.selected_device_ids.add(device_id)

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
            selected=(device_id in self.selected_device_ids),
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


# --- Dependency Manager ---
class DependencyManager:
    def __init__(self):
        self.rules: Dict[str, DependencyRule] = {}

    def list_rules(self) -> List[DependencyRule]:
        return list(self.rules.values())

    def add_rule(self, rule_create: DependencyRuleCreate) -> DependencyRule:
        rule_id = str(uuid.uuid4())
        target_topic = rule_create.target_topic.strip() or f"{rule_create.target_device_id}/command"

        rule = DependencyRule(
            id=rule_id,
            source_device_id=rule_create.source_device_id,
            source_emitter=rule_create.source_emitter,
            trigger_state=rule_create.trigger_state,
            target_device_id=rule_create.target_device_id,
            target_topic=target_topic,
            payload=rule_create.payload,
            enabled=rule_create.enabled,
        )
        self.rules[rule.id] = rule
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        if rule_id not in self.rules:
            return False
        del self.rules[rule_id]
        return True

    def get_matching_rules(self, source_device_id: str, emitter_id: str, is_active: bool) -> List[DependencyRule]:
        event_state = "on" if is_active else "off"
        matched: List[DependencyRule] = []
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            if rule.source_device_id != source_device_id:
                continue
            if rule.source_emitter != emitter_id:
                continue
            if rule.trigger_state not in {"any", event_state}:
                continue
            matched.append(rule)
        return matched


# --- Session Manager ---
class SessionManager:
    def __init__(self):
        self.active: bool = False
        self.matrix: SessionMatrix = SessionMatrix()
        # Active connections: source_id -> list of target_ids currently triggered
        self.active_connections: Dict[str, List[str]] = {}
        # Last known emitter state: "<source_id>:<emitter_id>" -> bool
        self.emitter_states: Dict[str, bool] = {}
        # Last known emitter state: "<source_id>:<emitter_id>" -> bool
        self.emitter_states: Dict[str, bool] = {}

    def start_session(self, selected_ids: List[str]) -> SessionMatrix:
        self.active = True
        self.active_connections.clear()
        self.emitter_states.clear()

        devices = sorted(selected_ids)
        n = len(devices)
        matrix_data = []

        if n > 0:
            for i in range(n):
                row = [0.0 if r == i else random.uniform(0, 0.3) for r in range(n)]

                if n > 1:
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
            return []

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
