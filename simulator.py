import paho.mqtt.client as mqtt
import json
import time
import random
import os

# --- Konfiguracja ---
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
NUM_DEVICES = 5
DEVICE_IDS = [f"sim_device_{i + 1}" for i in range(NUM_DEVICES)]

# --- Stan symulatora ---
device_clients = {}

# --- Logika MQTT dla symulatora ---


def on_connect(client, userdata, flags, rc):
    device_id = userdata["device_id"]
    print(f"[{device_id}] Connected to MQTT broker with result code {rc}")

    # Subskrypcja na komendy
    command_topic = f"{device_id}/command"
    client.subscribe(command_topic)
    print(f"[{device_id}] Subscribed to {command_topic}")

    # Publikacja statusu początkowego
    status_topic = f"{device_id}/status"
    status_payload = {
        "status": True,
        "charge_level": 100,
        "actuators": ["led"],
        "emitters": ["button"],
    }
    client.publish(status_topic, json.dumps(status_payload), retain=True)
    print(f"[{device_id}] Published initial status")


def on_message(client, userdata, msg):
    device_id = userdata["device_id"]
    print(f"[{device_id}] Received message on {msg.topic}: {msg.payload.decode()}")

    try:
        payload = json.loads(msg.payload.decode())
        if "state" in payload:
            led_state = "ON" if payload["state"] else "OFF"
            print(f"[{device_id}] Actuator triggered: LED is now {led_state}")
    except json.JSONDecodeError:
        print(f"[{device_id}] Failed to decode JSON: {msg.payload.decode()}")


def create_device_client(device_id: str):
    """Tworzy i konfiguruje klienta MQTT dla jednego urządzenia."""
    client = mqtt.Client(client_id=device_id, userdata={"device_id": device_id})
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, 1883, 60)
        client.loop_start()
        return client
    except Exception as e:
        print(f"[{device_id}] Failed to connect to MQTT broker: {e}")
        return None


# --- Główna pętla symulatora ---


def run_simulator():
    print("Starting device simulator...")

    for device_id in DEVICE_IDS:
        client = create_device_client(device_id)
        if client:
            device_clients[device_id] = client
            time.sleep(0.1)  # Rozłożenie połączeń w czasie

    if not device_clients:
        print("No devices could connect. Exiting simulator.")
        return

    print(f"Successfully started {len(device_clients)} simulated devices.")

    try:
        while True:
            # Losowe wyzwalanie "naciśnięcia przycisku"
            emitter_device_id = random.choice(list(device_clients.keys()))
            client = device_clients[emitter_device_id]

            sensor_topic = f"{emitter_device_id}/sensor"

            # Symulacja naciśnięcia (button_state: 0 -> pressed)
            press_payload = json.dumps({"button_state": 0})
            client.publish(sensor_topic, press_payload)
            print(f"[{emitter_device_id}] Event: Sensor ACTIVE (Pressed)")

            time.sleep(0.2)  # Krótkie opóźnienie symulujące czas naciśnięcia

            # Symulacja zwolnienia (button_state: 1 -> released)
            release_payload = json.dumps({"button_state": 1})
            client.publish(sensor_topic, release_payload)
            print(f"[{emitter_device_id}] Event: Sensor INACTIVE (Released)")

            # Czekaj losowy czas przed następnym zdarzeniem
            time.sleep(random.uniform(2, 5))

    except KeyboardInterrupt:
        print("\nStopping simulator...")
    finally:
        for device_id, client in device_clients.items():
            # Publikacja statusu offline
            status_topic = f"{device_id}/status"
            status_payload = {"status": False}
            client.publish(status_topic, json.dumps(status_payload), retain=True)

            client.loop_stop()
            client.disconnect()
            print(f"[{device_id}] Disconnected.")


if __name__ == "__main__":
    run_simulator()
