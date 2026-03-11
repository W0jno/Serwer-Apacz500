#!/usr/bin/env python3
"""Referencyjny klient widgetu dla serwera MQTT.

Uruchom na urządzeniu i ustaw zmienne środowiskowe:
- WIDGET_ID (np. widget_001)
- MQTT_HOST (domyślnie localhost)
- MQTT_PORT (domyślnie 1883)
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass

import paho.mqtt.client as mqtt


@dataclass
class DeviceConfig:
    device_id: str
    mqtt_host: str
    mqtt_port: int


class WidgetClient:
    def __init__(self, config: DeviceConfig) -> None:
        self.config = config
        self.running = True
        self.state = False  # stan LED/aktuatora
        self.button_pressed = False
        self.charge_level = 100

        self.client = mqtt.Client(client_id=self.config.device_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    @property
    def command_topic(self) -> str:
        return f"{self.config.device_id}/command"

    @property
    def status_topic(self) -> str:
        return f"{self.config.device_id}/status"

    @property
    def sensor_topic(self) -> str:
        return f"{self.config.device_id}/sensor"

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc) -> None:
        if rc != 0:
            print(f"[ERROR] Nie udało się połączyć z brokerem, rc={rc}")
            return

        print(f"[OK] Połączono z {self.config.mqtt_host}:{self.config.mqtt_port}")
        client.subscribe(self.command_topic)
        print(f"[OK] Subskrypcja: {self.command_topic}")
        self.publish_status(retain=True)

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            print(f"[WARN] Nieprawidłowy JSON na {msg.topic}: {msg.payload!r}")
            return

        if "state" in payload:
            self.state = bool(payload["state"])
            print(f"[CMD] Otrzymano komendę: state={self.state}")
            self.publish_status(retain=True)

    def publish_status(self, retain: bool = True) -> None:
        payload = {
            "status": True,
            "charge_level": self.charge_level,
            "actuators": ["led"],
            "emitters": ["button"],
        }
        self.client.publish(self.status_topic, json.dumps(payload), qos=1, retain=retain)
        print(f"[PUB] {self.status_topic} -> {payload}")

    def publish_sensor(self, pressed: bool) -> None:
        sensor_value = 0 if pressed else 1
        payload = {"sensor_value": sensor_value}
        self.client.publish(self.sensor_topic, json.dumps(payload), qos=0, retain=False)
        print(f"[PUB] {self.sensor_topic} -> {payload}")

    def start(self) -> None:
        self.client.connect(self.config.mqtt_host, self.config.mqtt_port, 60)
        self.client.loop_start()

        def status_heartbeat() -> None:
            while self.running:
                time.sleep(10)
                if not self.running:
                    break
                self.publish_status(retain=True)

        threading.Thread(target=status_heartbeat, daemon=True).start()

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        offline_payload = {
            "status": False,
            "charge_level": self.charge_level,
            "actuators": ["led"],
            "emitters": ["button"],
        }
        self.client.publish(self.status_topic, json.dumps(offline_payload), qos=1, retain=True)
        self.client.loop_stop()
        self.client.disconnect()
        print("[OK] Klient zatrzymany")


def main() -> int:
    config = DeviceConfig(
        device_id=os.getenv("WIDGET_ID", "widget_001"),
        mqtt_host=os.getenv("MQTT_HOST", "localhost"),
        mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
    )

    widget = WidgetClient(config)

    def handle_signal(_sig, _frame):
        widget.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    widget.start()

    print("\nSterowanie testowe:")
    print("- naciśnij ENTER: wysyła button PRESS + RELEASE")
    print("- wpisz 'on'/'off': lokalna zmiana stanu i status")
    print("- wpisz 'q': wyjście\n")

    while True:
        cmd = input("> ").strip().lower()
        if cmd == "q":
            widget.stop()
            return 0
        if cmd == "on":
            widget.state = True
            widget.publish_status(retain=True)
            continue
        if cmd == "off":
            widget.state = False
            widget.publish_status(retain=True)
            continue

        widget.publish_sensor(pressed=True)
        time.sleep(0.2)
        widget.publish_sensor(pressed=False)


if __name__ == "__main__":
    raise SystemExit(main())
