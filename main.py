import json
import os
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=True,
    engineio_logger=True,
    allow_upgrades=False,
    transports=["polling"],
)

device_data = {}
selected_devices = set()
session_active = False
mqtt_client = None


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe("+/status")
    print("Subscribed to +/status topics")


def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        device_id = topic.split("/")[0]
        payload = json.loads(msg.payload.decode())

        device_status = payload.get("status", False)
        charge_level = payload.get("charge_level", 0)

        # Add new devices to selected set by default
        if device_id not in device_data:
            selected_devices.add(device_id)

        device_data[device_id] = {
            "status": device_status,
            "charge_level": charge_level,
            "last_updated": datetime.now().isoformat(),
            "topic": topic,
            "selected": device_id in selected_devices,
        }

        operational = "operational" if device_status else "not operational"
        print(f"Updated device {device_id}: {operational}, charge={charge_level}%")

        socketio.emit(
            "device_update", {"device_id": device_id, "data": device_data[device_id]}
        )

    except json.JSONDecodeError:
        print(f"Failed to decode JSON from topic {msg.topic}: {msg.payload}")
    except Exception as e:
        print(f"Error processing message: {e}")


def init_mqtt():
    global mqtt_client
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        mqtt_host = os.getenv("MQTT_HOST", "localhost")
        mqtt_client.connect(mqtt_host, 1883, 60)
        mqtt_client.loop_start()
        print(f"MQTT client started, connected to {mqtt_host}")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/devices")
def get_devices():
    return jsonify(device_data)


@socketio.on("connect")
def handle_connect():
    client_id = request.sid if "request" in globals() else "unknown"
    print(f"Client connected: {client_id}")
    emit("devices_data", device_data)
    emit(
        "connection_confirmed",
        {"status": "connected", "server_time": datetime.now().isoformat()},
    )


@socketio.on("device_selected")
def handle_device_selection(data):
    device_id = data.get("device_id")
    is_selected = data.get("selected", False)

    if is_selected:
        selected_devices.add(device_id)
    else:
        selected_devices.discard(device_id)

    if device_id in device_data:
        device_data[device_id]["selected"] = is_selected

    print(f"Device {device_id} {'selected' if is_selected else 'deselected'}")
    print(f"Currently selected devices: {list(selected_devices)}")


@socketio.on("disconnect")
def handle_disconnect():
    client_id = request.sid if "request" in globals() else "unknown"
    print(f"Client disconnected: {client_id}")


@app.route("/api/selected-devices")
def get_selected_devices():
    return jsonify(list(selected_devices))


@socketio.on("start_session")
def handle_start_session():
    global session_active
    session_active = True
    print("Session started")
    socketio.emit("session_status", {"active": True, "action": "started"})


@socketio.on("stop_session")
def handle_stop_session():
    global session_active
    session_active = False
    print("Session stopped")
    socketio.emit("session_status", {"active": False, "action": "stopped"})


def cleanup_old_devices():
    while True:
        try:
            current_time = datetime.now()
            devices_to_remove = []

            for device_id, data in device_data.items():
                last_updated = datetime.fromisoformat(data["last_updated"])
                if (current_time - last_updated).total_seconds() > 300:
                    devices_to_remove.append(device_id)

            for device_id in devices_to_remove:
                del device_data[device_id]
                socketio.emit("device_removed", {"device_id": device_id})
                print(f"Removed inactive device: {device_id}")

        except Exception as e:
            print(f"Error in cleanup thread: {e}")

        time.sleep(60)


if __name__ == "__main__":
    init_mqtt()
    cleanup_thread = threading.Thread(target=cleanup_old_devices, daemon=True)
    cleanup_thread.start()
    print("Starting Flask webapp on http://0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
