#!/usr/bin/env python3
"""
Mock MQTT publisher for testing device status dashboard.
Publishes fake device status messages including hardware capabilities (actuators/emitters).
"""

import json
import os
import random
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt

# --- BAZA MOŻLIWYCH KOMPONENTÓW ---
POSSIBLE_ACTUATORS = [
    "Button_Main", "Button_Reset", "Switch_A", "Switch_B", 
    "Proximity_Sensor", "Reed_Switch", "Touch_Panel"
]

POSSIBLE_EMITTERS = [
    "Green_LED", "Red_LED", "Blue_LED", "Buzzer", 
    "LCD_Screen", "Relay_Output", "Status_Beep"
]

class MockDevice:
    def __init__(self, device_id, initial_charge=None):
        self.device_id = device_id
        self.charge_level = initial_charge or random.randint(20, 100)
        self.status = True  # operational status
        self.charge_trend = random.choice([-1, 1])  # -1 for draining, 1 for charging
        
        # Losowe przydzielanie sprzętu (1 do 3 elementów każdego typu)
        self.actuators = random.sample(POSSIBLE_ACTUATORS, k=random.randint(1, 3))
        self.emitters = random.sample(POSSIBLE_EMITTERS, k=random.randint(1, 3))

    def update(self):
        """Update device operational status and charge level."""
        # Randomly change operational status (90% chance to stay the same)
        if random.random() < 0.1:
            self.status = not self.status

        # Update charge level
        if self.status:  # Only update charge if device is operational
            # Change charge level by -3 to +5 percent
            charge_change = random.randint(-3, 5)

            # If charging, bias towards positive change
            if self.charge_trend == 1:
                charge_change = random.randint(-1, 8)
            else:  # draining
                charge_change = random.randint(-5, 2)

            self.charge_level = max(0, min(100, self.charge_level + charge_change))

            # Switch charging/draining trend at extremes
            if self.charge_level <= 10:
                self.charge_trend = 1  # start charging
            elif self.charge_level >= 95:
                self.charge_trend = -1  # start draining
            elif random.random() < 0.05:  # 5% chance to randomly switch
                self.charge_trend *= -1

    def to_json(self):
        """Convert device state to JSON message."""
        return json.dumps(
            {
                "status": self.status,
                "charge_level": self.charge_level,
                "timestamp": datetime.now().isoformat(),
                "trend": "charging" if self.charge_trend == 1 else "draining",
                "actuators": self.actuators,
                "emitters": self.emitters
            }
        )


class MockMQTTPublisher:
    def __init__(self, broker_host=None, broker_port=1883):
        self.broker_host = broker_host or os.getenv("MQTT_HOST", "localhost")
        self.broker_port = broker_port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        self.devices = {}
        self.running = False

        # Create some mock devices
        device_names = [
            "sensor_001",
            "sensor_002",
            "sensor_003",
            "sensor_004",
            "sensor_005",
            "sensor_006",
            "sensor_007",
            "sensor_008",
            "sensor_009",
            "sensor_010",
            "sensor_011",
        ]

        for name in device_names:
            self.devices[name] = MockDevice(name)

    def on_connect(self, client, userdata, flags, rc):
        """Callback for when the client receives a CONNACK response."""
        if rc == 0:
            print(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
        else:
            print(f"Failed to connect to MQTT broker. Return code: {rc}")

    def on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects."""
        print("Disconnected from MQTT broker")

    def connect(self):
        """Connect to the MQTT broker."""
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

        try:
            print(
                f"Attempting to connect to MQTT broker at {self.broker_host}:{self.broker_port}"
            )
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            print(
                f"Make sure the broker is running and accessible at {self.broker_host}:{self.broker_port}"
            )
            return False

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()

    def publish_device_status(self, device_id, device):
        """Publish status for a single device."""
        topic = f"{device_id}/status"
        message = device.to_json()

        try:
            result = self.client.publish(topic, message)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                status_text = "operational" if device.status else "not operational"
                # Skrócony log, żeby nie zaśmiecać konsoli listami sprzętu
                print(f"Published {device_id}: {status_text}, {device.charge_level}% (HW: {len(device.actuators)}A/{len(device.emitters)}E)")
            else:
                print(f"Failed to publish to {topic}")
        except Exception as e:
            print(f"Error publishing to {topic}: {e}")

    def run_simulation(self, update_interval=5):
        """Run the device simulation."""
        print(f"Starting simulation with {len(self.devices)} devices")
        print(f"Update interval: {update_interval} seconds")
        print("Press Ctrl+C to stop")

        self.running = True

        try:
            while self.running:
                # Update and publish status for each device
                for device_id, device in self.devices.items():
                    device.update()
                    self.publish_device_status(device_id, device)

                # Add some randomness - sometimes skip a device
                if random.random() < 0.1:
                    skip_device = random.choice(list(self.devices.keys()))
                    print(f"Skipping update for {skip_device} this cycle")

                time.sleep(update_interval)

        except KeyboardInterrupt:
            print("\nStopping simulation...")
        finally:
            self.disconnect()

    def add_device(self, device_id, initial_charge=None):
        """Add a new device to the simulation."""
        self.devices[device_id] = MockDevice(device_id, initial_charge)
        print(f"Added device: {device_id}")

    def remove_device(self, device_id):
        """Remove a device from the simulation."""
        if device_id in self.devices:
            del self.devices[device_id]
            print(f"Removed device: {device_id}")

    def list_devices(self):
        """List all devices and their current status."""
        print("\nCurrent devices:")
        print("-" * 80)
        print(f"{'DEVICE ID':<15} | {'STATUS':<10} | {'BAT':<4} | {'ACTUATORS':<20} | {'EMITTERS'}")
        print("-" * 80)
        for device_id, device in self.devices.items():
            status = "OK" if device.status else "ERR"
            trend = "↑" if device.charge_trend == 1 else "↓"
            act_str = ",".join(device.actuators)[:20] # truncate for display
            emit_str = ",".join(device.emitters)
            print(f"{device_id:<15} | {status:<10} | {device.charge_level:3d}%{trend} | {act_str:<20} | {emit_str}")
        print("-" * 80)


def main():
    """Main function to run the mock publisher."""
    print("MQTT Device Status Mock Publisher v2.0")
    print("=" * 40)

    publisher = MockMQTTPublisher()

    if not publisher.connect():
        mqtt_host = os.getenv("MQTT_HOST", "localhost")
        print(
            f"Failed to connect to MQTT broker. Make sure it's running on {mqtt_host}:1883"
        )
        return

    # Wait a moment for connection to establish
    time.sleep(1)

    # Show initial device list with hardware details
    publisher.list_devices()

    try:
        # Run the simulation (publishes every 5 seconds)
        publisher.run_simulation(update_interval=200)

    except Exception as e:
        print(f"Error running simulation: {e}")
    finally:
        publisher.disconnect()


if __name__ == "__main__":
    main()