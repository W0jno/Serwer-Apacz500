import asyncio
import json
import os
from typing import Any, Dict

import paho.mqtt.client as mqtt

from .managers import ConnectionManager, DependencyManager, DeviceManager, SessionManager
from .models import WebSocketMessage


class MQTTService:
    def __init__(
        self,
        device_manager: DeviceManager,
        session_manager: SessionManager,
        connection_manager: ConnectionManager,
        dependency_manager: DependencyManager,
    ):
        self.device_manager = device_manager
        self.session_manager = session_manager
        self.connection_manager = connection_manager
        self.dependency_manager = dependency_manager
        self.client = mqtt.Client()
        self.loop = asyncio.get_event_loop()
        self.dependency_emitter_states: Dict[str, bool] = {}

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def start(self):
        mqtt_host = os.getenv("MQTT_HOST", "localhost")
        try:
            self.client.connect(mqtt_host, 1883, 60)
            self.client.loop_start()
            print(f"MQTT Service started, connected to {mqtt_host}")
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish_command(self, device_id: str, payload: Dict[str, Any]) -> bool:
        topic = f"{device_id}/command"
        return self.publish_topic(topic, payload)

    def publish_topic(self, topic: str, payload: Dict[str, Any]) -> bool:
        try:
            payload_str = json.dumps(payload)
            result = self.client.publish(topic, payload_str)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"Published command to {topic}: {payload_str}")
                return True
            print(f"Failed to publish command to {topic}, rc={result.rc}")
            return False
        except Exception as e:
            print(f"Error publishing command to topic {topic}: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        client.subscribe("+/status")
        client.subscribe("+/sensor")

    def _on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split("/")
            if len(topic_parts) < 2:
                return

            device_id = topic_parts[0]
            topic_type = topic_parts[1]
            payload = json.loads(msg.payload.decode())

            if topic_type == "status":
                self._handle_status(device_id, payload, msg.topic)
            elif topic_type == "sensor":
                self._handle_sensor(device_id, payload)

        except json.JSONDecodeError:
            print(f"Failed to decode JSON from topic {msg.topic}")
        except Exception as e:
            print(f"Error processing message: {e}")

    def _handle_status(self, device_id: str, payload: dict, topic: str):
        device_state = self.device_manager.update_device(device_id, payload, topic)

        message = WebSocketMessage(
            event="device_update",
            data={"device_id": device_id, "data": device_state.model_dump(mode='json')},
        )
        self._broadcast_async(message)

    def _normalize_sensor_state(self, payload: dict) -> tuple[bool | None, Any, str]:
        emitter_id = str(payload.get("emitter", "default"))
        raw_value = payload.get("value", payload.get("sensor_value"))

        if raw_value is None:
            return None, None, emitter_id

        if isinstance(raw_value, bool):
            return raw_value, raw_value, emitter_id

        if isinstance(raw_value, (int, float)):
            return raw_value != 0, raw_value, emitter_id

        if isinstance(raw_value, str):
            text = raw_value.strip().lower()
            if text in {"1", "true", "on", "pressed", "active", "high"}:
                return True, raw_value, emitter_id
            if text in {"0", "false", "off", "released", "inactive", "low"}:
                return False, raw_value, emitter_id
            return len(text) > 0, raw_value, emitter_id

        return bool(raw_value), raw_value, emitter_id

    def _handle_dependency_rules(self, device_id: str, emitter_id: str, is_active: bool, payload: dict):
        dep_key = f"{device_id}:{emitter_id}"
        previous_state = self.dependency_emitter_states.get(dep_key)
        if previous_state is not None and previous_state == is_active:
            return
        self.dependency_emitter_states[dep_key] = is_active

        matched_rules = self.dependency_manager.get_matching_rules(device_id, emitter_id, is_active)
        if not matched_rules:
            return

        for rule in matched_rules:
            outgoing_payload = dict(rule.payload)
            outgoing_payload.setdefault("source_device", device_id)
            outgoing_payload.setdefault("emitter", emitter_id)
            outgoing_payload.setdefault("sensor_value", payload.get("sensor_value"))
            outgoing_payload.setdefault("value", payload.get("value", payload.get("sensor_value")))
            outgoing_payload.setdefault("state", is_active)
            self.publish_topic(rule.target_topic, outgoing_payload)

    def _handle_sensor(self, device_id: str, payload: dict):
        is_active, raw_value, emitter_id = self._normalize_sensor_state(payload)
        if is_active is None:
            return

        self._handle_dependency_rules(device_id, emitter_id, is_active, payload)

        if not self.session_manager.active:
            return

        targets = self.session_manager.handle_emitter_event(device_id, emitter_id, is_active)
        if not targets:
            return

        action = "ON" if is_active else "OFF"
        if is_active:
            print(f"Device {device_id} emitter '{emitter_id}' active (value={raw_value}). Evaluating connections...")
        else:
            print(f"Device {device_id} emitter '{emitter_id}' inactive (value={raw_value}). Deactivating connections...")

        payload_cmd = {
            "state": is_active,
            "source_device": device_id,
            "emitter": emitter_id,
            "sensor_value": payload.get("sensor_value"),
            "value": payload.get("value", payload.get("sensor_value")),
        }

        for target_id in targets:
            print(f"  --> Triggering {target_id} {action}")
            self.publish_command(target_id, payload_cmd)

    def _broadcast_async(self, message: WebSocketMessage):
        """Helper to run async broadcast from sync MQTT thread."""
        asyncio.run_coroutine_threadsafe(self.connection_manager.broadcast(message), self.loop)
