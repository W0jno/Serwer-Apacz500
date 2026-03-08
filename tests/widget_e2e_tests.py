#!/usr/bin/env python3
"""E2E testy MQTT/FastAPI dla widgetów ESP32.

Scenariusze:
1) LED + button: backend wysyła komendy ON/OFF na <device_id>/command.
2) Emitter z wartością float: float != 0 aktywuje, a 0 dezaktywuje połączenie.
3) Połączenie 2 widgetów: klik w źródle -> komenda LED ON/OFF w celu.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import paho.mqtt.client as mqtt
import websockets

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
WS_URL = os.getenv("WS_URL", "ws://localhost:5000/ws")
API_DEVICES_URL = os.getenv("API_DEVICES_URL", "http://localhost:5000/api/devices")


@dataclass
class TopicRecorder:
    topic: str
    messages: list[dict[str, Any]] = field(default_factory=list)

    def push(self, payload: bytes) -> None:
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError:
            decoded = {"_raw": payload.decode("utf-8", errors="replace")}
        self.messages.append(decoded)

    def wait_for(self, predicate, timeout_s: float = 5.0) -> dict[str, Any] | None:
        deadline = time.time() + timeout_s
        seen = 0
        while time.time() < deadline:
            while seen < len(self.messages):
                msg = self.messages[seen]
                seen += 1
                if predicate(msg):
                    return msg
            time.sleep(0.05)
        return None


class MqttHarness:
    def __init__(self) -> None:
        self.recorders: dict[str, TopicRecorder] = {}
        self.client = mqtt.Client(client_id=f"widget-test-{int(time.time()*1000)}")
        self.client.on_message = self._on_message

    def connect(self) -> None:
        self.client.connect(MQTT_HOST, MQTT_PORT, 60)
        self.client.loop_start()

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def subscribe(self, topic: str) -> TopicRecorder:
        rec = TopicRecorder(topic=topic)
        self.recorders[topic] = rec
        self.client.subscribe(topic)
        return rec

    def publish(self, topic: str, payload: dict[str, Any], retain: bool = False, qos: int = 0) -> None:
        self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def _on_message(self, _client, _userdata, msg: mqtt.MQTTMessage) -> None:
        rec = self.recorders.get(msg.topic)
        if rec is not None:
            rec.push(msg.payload)


async def ws_send_event(event: str, data: dict[str, Any]) -> None:
    async with websockets.connect(WS_URL) as ws:
        await ws.recv()
        await ws.recv()
        await ws.recv()
        await ws.send(json.dumps({"event": event, "data": data}))
        await asyncio.sleep(0.2)


async def ws_configure_pair_and_start_session(a: str, b: str) -> dict[str, Any]:
    async with websockets.connect(WS_URL) as ws:
        await ws.recv()  # connection_confirmed
        devices_data = json.loads(await ws.recv())
        await ws.recv()  # session_status

        all_devices = devices_data.get("data", {}).keys()
        for dev_id in all_devices:
            should_select = dev_id in {a, b}
            await ws.send(
                json.dumps(
                    {
                        "event": "device_selected",
                        "data": {"device_id": dev_id, "selected": should_select},
                    }
                )
            )
            await asyncio.sleep(0.02)

        await ws.send(json.dumps({"event": "start_session", "data": {}}))

        deadline = time.time() + 8
        while time.time() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=8)
            payload = json.loads(raw)
            if payload.get("event") == "session_matrix_update":
                return payload["data"]

        raise AssertionError("Nie otrzymano session_matrix_update")


def get_devices() -> dict[str, Any]:
    with urllib.request.urlopen(API_DEVICES_URL, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_1_led_and_button(h: MqttHarness) -> None:
    print("[TEST1] LED + button")
    device_id = f"test_led_button_{int(time.time())}"
    command_topic = f"{device_id}/command"

    rec = h.subscribe(command_topic)

    h.publish(
        f"{device_id}/status",
        {
            "status": True,
            "charge_level": 98,
            "actuators": ["led"],
            "emitters": ["button"],
        },
        retain=True,
        qos=1,
    )

    asyncio.run(ws_send_event("device_status_change", {"device_id": device_id, "status": True}))
    msg_on = rec.wait_for(lambda m: m.get("state") is True, timeout_s=5)
    assert msg_on is not None, "Nie przyszła komenda LED ON"

    asyncio.run(ws_send_event("device_status_change", {"device_id": device_id, "status": False}))
    msg_off = rec.wait_for(lambda m: m.get("state") is False, timeout_s=5)
    assert msg_off is not None, "Nie przyszła komenda LED OFF"
    print("[TEST1] OK")


def test_2_float_emitter(h: MqttHarness) -> None:
    print("[TEST2] Emitter float (aktywny w sesji)")
    ts = int(time.time())
    source = f"test_float_src_{ts}"
    target = f"test_float_tgt_{ts}"

    target_rec = h.subscribe(f"{target}/command")

    h.publish(
        f"{source}/status",
        {
            "status": True,
            "charge_level": 87,
            "actuators": ["relay"],
            "emitters": ["gyro"],
        },
        retain=True,
        qos=1,
    )
    h.publish(
        f"{target}/status",
        {
            "status": True,
            "charge_level": 93,
            "actuators": ["light_strip"],
            "emitters": ["temp_sensor"],
        },
        retain=True,
        qos=1,
    )
    time.sleep(0.8)

    devices = get_devices()
    assert source in devices, "Źródło float nie pojawiło się w /api/devices"
    assert target in devices, "Target float nie pojawił się w /api/devices"
    assert "gyro" in devices[source].get("emitters", []), "Emitter 'gyro' nie zapisany"

    matrix = asyncio.run(ws_configure_pair_and_start_session(source, target))
    matrix_devices = matrix["devices"]
    probs = matrix["matrix"]

    # Znajdź relację 1.0 pomiędzy source/target (kierunek może być różny)
    src = None
    tgt = None
    for i, row in enumerate(probs):
        for j, p in enumerate(row):
            if p == 1.0 and matrix_devices[i] in (source, target) and matrix_devices[j] in (source, target):
                src = matrix_devices[i]
                tgt = matrix_devices[j]
                break
        if src:
            break

    assert src is not None and tgt is not None, "Brak relacji 1.0 dla pary float"
    active_rec = target_rec if tgt == target else h.subscribe(f"{source}/command")

    # Wartość float != 0 => aktywacja (ON)
    h.publish(f"{src}/sensor", {"emitter": "gyro", "sensor_value": 0.42, "value": 0.42})
    on_msg = active_rec.wait_for(lambda m: m.get("state") is True, timeout_s=5)
    assert on_msg is not None, "Brak komendy ON dla float=0.42"

    # Wartość float == 0 => dezaktywacja (OFF)
    h.publish(f"{src}/sensor", {"emitter": "gyro", "sensor_value": 0.0, "value": 0.0})
    off_msg = active_rec.wait_for(lambda m: m.get("state") is False, timeout_s=5)
    assert off_msg is not None, "Brak komendy OFF dla float=0.0"

    print(f"[TEST2] OK ({src} -> {tgt})")


def test_3_two_widgets_communication(h: MqttHarness) -> None:
    print("[TEST3] Dwa widgety: button -> led")
    ts = int(time.time())
    a = f"test_pair_a_{ts}"
    b = f"test_pair_b_{ts}"

    rec_a = h.subscribe(f"{a}/command")
    rec_b = h.subscribe(f"{b}/command")

    h.publish(
        f"{a}/status",
        {
            "status": True,
            "charge_level": 100,
            "actuators": ["relay"],
            "emitters": ["button"],
        },
        retain=True,
        qos=1,
    )
    h.publish(
        f"{b}/status",
        {
            "status": True,
            "charge_level": 99,
            "actuators": ["led"],
            "emitters": ["gyro"],
        },
        retain=True,
        qos=1,
    )

    time.sleep(0.8)

    matrix = asyncio.run(ws_configure_pair_and_start_session(a, b))
    devices = matrix["devices"]
    probs = matrix["matrix"]

    source = None
    target = None
    for i, row in enumerate(probs):
        for j, p in enumerate(row):
            if p == 1.0 and devices[i] in (a, b) and devices[j] in (a, b):
                source = devices[i]
                target = devices[j]
                break
        if source:
            break

    assert source is not None and target is not None, "Brak relacji 1.0 między testowymi widgetami"

    target_rec = rec_a if target == a else rec_b

    h.publish(f"{source}/sensor", {"sensor_value": 0, "emitter": "button", "value": 0})
    on_msg = target_rec.wait_for(lambda m: m.get("state") is True, timeout_s=5)
    assert on_msg is not None, "Target nie dostał komendy ON po press"

    h.publish(f"{source}/sensor", {"sensor_value": 1, "emitter": "button", "value": 1})
    off_msg = target_rec.wait_for(lambda m: m.get("state") is False, timeout_s=5)
    assert off_msg is not None, "Target nie dostał komendy OFF po release"

    print(f"[TEST3] OK ({source} -> {target})")


def main() -> int:
    print(f"MQTT={MQTT_HOST}:{MQTT_PORT}")
    print(f"WS={WS_URL}")
    print(f"API={API_DEVICES_URL}")

    harness = MqttHarness()
    try:
        harness.connect()
    except Exception as exc:
        print(f"[ERROR] Brak połączenia z MQTT ({MQTT_HOST}:{MQTT_PORT}): {exc}")
        print("Uruchom najpierw serwisy, np. docker compose up -d mosquitto fastapi")
        return 2

    try:
        test_1_led_and_button(harness)
        test_2_float_emitter(harness)
        test_3_two_widgets_communication(harness)
    finally:
        harness.close()

    print("\nWszystkie testy przeszły.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
