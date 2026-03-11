import asyncio
import json
import os
import random
from typing import List

import paho.mqtt.client as mqtt

# --- Configuration ---
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
NUM_DEVICES = 10

class SimulatedDevice:
    def __init__(self, device_id: str, mqtt_host: str):
        self.device_id = device_id
        self.mqtt_host = mqtt_host
        self.client = mqtt.Client(client_id=device_id)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        
        self.status = True
        self.charge_level = random.randint(10, 95)
        self.running = False
        self.tasks: List[asyncio.Task] = []

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[{self.device_id}] Connected.")
            client.subscribe(f"{self.device_id}/command")
            self._publish_status()
        else:
            print(f"[{self.device_id}] Connection failed: {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if "state" in payload:
                self.status = payload["state"]
                state_str = "ON" if self.status else "OFF"
                print(f"[{self.device_id}] Actuator LED -> {state_str}")
                self._publish_status()
        except Exception as e:
            print(f"[{self.device_id}] Error decoding msg: {e}")

    def _publish_status(self):
        topic = f"{self.device_id}/status"
        payload = {
            "status": self.status,
            "charge_level": self.charge_level,
            "actuators": ["led"],
            "emitters": ["button"],
        }
        self.client.publish(topic, json.dumps(payload), retain=True)

    def start(self):
        try:
            self.client.connect(self.mqtt_host, 1883, 60)
            self.client.loop_start()
            self.running = True
            return True
        except Exception as e:
            print(f"[{self.device_id}] Connection error: {e}")
            return False

    async def stop(self):
        self.running = False
        for task in self.tasks:
            task.cancel()
        
        # Publish offline status
        self.client.publish(f"{self.device_id}/status", json.dumps({"status": False}), retain=True)
        
        self.client.loop_stop()
        self.client.disconnect()
        print(f"[{self.device_id}] Stopped.")

    async def behavior_loop(self):
        """Simulates random button presses."""
        while self.running:
            # Random wait between interactions
            await asyncio.sleep(random.uniform(2, 15))
            
            if not self.running:
                break

            # Press
            print(f"[{self.device_id}] Button PRESSED")
            self.client.publish(f"{self.device_id}/sensor", json.dumps({"sensor_value": 0}))
            
            # Hold duration
            await asyncio.sleep(0.3)
            
            # Release
            print(f"[{self.device_id}] Button RELEASED")
            self.client.publish(f"{self.device_id}/sensor", json.dumps({"sensor_value": 1}))

    async def status_loop(self):
        """Periodically updates status (charge level, etc)."""
        while self.running:
            await asyncio.sleep(10)
            if not self.running:
                break
            
            # Simulate battery drain/charge
            self.charge_level += random.choice([-1, 0, 1])
            self.charge_level = max(0, min(100, self.charge_level))
            self._publish_status()


async def run_simulator():
    print(f"Starting simulator for {NUM_DEVICES} devices on {MQTT_HOST}...")
    devices: List[SimulatedDevice] = []

    # Create and start devices
    for i in range(NUM_DEVICES):
        dev = SimulatedDevice(f"sim_device_{i+1:03d}", MQTT_HOST)
        if dev.start():
            devices.append(dev)
            # Stagger startup to avoid connection spikes
            await asyncio.sleep(0.1)

    print("All devices started. Press Ctrl+C to stop.")

    # Start behavior tasks
    tasks = []
    for dev in devices:
        t1 = asyncio.create_task(dev.behavior_loop())
        t2 = asyncio.create_task(dev.status_loop())
        dev.tasks.extend([t1, t2])
        tasks.extend([t1, t2])

    try:
        # Keep running until cancelled
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        print("Cleaning up...")
        for dev in devices:
            await dev.stop()

if __name__ == "__main__":
    try:
        asyncio.run(run_simulator())
    except KeyboardInterrupt:
        pass