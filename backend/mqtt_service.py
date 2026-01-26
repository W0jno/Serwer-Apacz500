import asyncio
import json
import os
from typing import Dict, Any

import paho.mqtt.client as mqtt
from .managers import DeviceManager, SessionManager, ConnectionManager
from .models import WebSocketMessage

class MQTTService:
    def __init__(
        self, 
        device_manager: DeviceManager, 
        session_manager: SessionManager, 
        connection_manager: ConnectionManager
    ):
        self.device_manager = device_manager
        self.session_manager = session_manager
        self.connection_manager = connection_manager
        self.client = mqtt.Client()
        self.loop = asyncio.get_event_loop()
        
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
        try:
            payload_str = json.dumps(payload)
            result = self.client.publish(topic, payload_str)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"Published command to {topic}: {payload_str}")
                return True
            else:
                print(f"Failed to publish command to {topic}, rc={result.rc}")
                return False
        except Exception as e:
            print(f"Error publishing command to {device_id}: {e}")
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
        # Update device state
        device_state = self.device_manager.update_device(device_id, payload, topic)
        
        # Broadcast update to frontend
        message = WebSocketMessage(
            event="device_update",
            data={"device_id": device_id, "data": device_state.model_dump(mode='json')}
        )
        self._broadcast_async(message)

    def _handle_sensor(self, device_id: str, payload: dict):
        if not self.session_manager.active:
            return

        sensor_value = payload.get("sensor_value")
        if sensor_value is None:
            return

        targets = []
        action = ""

        if sensor_value == 0:  # Pressed
            print(f"Device {device_id} pressed. Evaluating connections...")
            targets = self.session_manager.handle_button_press(device_id)
            action = "ON"
            payload_cmd = {"state": True}
        
        elif sensor_value == 1:  # Released
            targets = self.session_manager.handle_button_release(device_id)
            if targets:
                print(f"Device {device_id} released. Deactivating connections...")
            action = "OFF"
            payload_cmd = {"state": False}

        for target_id in targets:
            print(f"  --> Triggering {target_id} {action}")
            self.publish_command(target_id, payload_cmd)

    def _broadcast_async(self, message: WebSocketMessage):
        """Helper to run async broadcast from sync MQTT thread."""
        asyncio.run_coroutine_threadsafe(
            self.connection_manager.broadcast(message), 
            self.loop
        )
