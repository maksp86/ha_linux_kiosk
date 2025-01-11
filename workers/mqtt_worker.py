import paho.mqtt.client as mqtt
import os
import queue
import json
import platform
import time
from threading import Thread, RLock

from const.available_commands import AVAILABLE_COMMANDS
from const.sensors import SENSORS
from workers.system_worker import SystemWorker


class MQTTWorker:
    def __init__(self, UNIQUE_ID: str, MAC_ADDR: str, MESSAGE_QUEUE: queue.Queue, SystemWorker: SystemWorker):
        self.UNIQUE_ID = UNIQUE_ID
        self.MAC_ADDR = MAC_ADDR
        self.MESSAGE_QUEUE = MESSAGE_QUEUE

        self.BASE_TOPIC = f"homeassistant/device/{self.UNIQUE_ID}/"
        self.COMMAND_TOPIC = self.BASE_TOPIC + "command"
        self.STATE_TOPIC = self.BASE_TOPIC + "state"
        self.AVAILABILITY_TOPIC = self.BASE_TOPIC + "availability"

        self.systemWorker = SystemWorker
        self.sensors_data = {}

        self.worker_queue = queue.Queue()

        self.mqtt_client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, UNIQUE_ID)

        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message

        if os.getenv("MQTT_USERNAME") != None and os.getenv("MQTT_PASSWORD") != None:
            self.mqtt_client.username_pw_set(
                os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD"))

        self.mqtt_client.will_set(self.AVAILABILITY_TOPIC,
                                  payload="offline", retain=True)

        self.worker_thread = Thread(target=self._timer, name="mqtt_send_timer")

    def start(self):
        if self.mqtt_client.is_connected():
            return

        self.mqtt_client.connect_async(os.getenv("MQTT_HOST"),
                                       int(os.getenv("MQTT_PORT")))

        self.mqtt_client.loop_start()

    def stop(self):
        if not self.mqtt_client.is_connected():
            return

        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()

    def push_command(self, message):
        self.worker_queue.put(message)

    def _ha_discovery(self, client: mqtt.Client):
        template = {
            "dev": {
                "identifiers": [self.UNIQUE_ID, self.MAC_ADDR.replace(":", "").lower()],
                "connections": [["mac", self.MAC_ADDR]],
                "name": f"{platform.node()} kiosk",
                "manufacturer": "maksp",
                "model": platform.machine(),
                "serial_number": self.MAC_ADDR.replace(":", "")[-6:],
                "sw_version": platform.version(),
            },
            "origin": {
                "name": "kiosk-script",
                "sw_version": "0.1"
            },
            "components": {

            },
            "state_topic": self.STATE_TOPIC,
            "command_topic": self.COMMAND_TOPIC,
            "availability_topic": self.AVAILABILITY_TOPIC
        }

        for sensor in SENSORS:
            template["components"][f"{
                self.UNIQUE_ID}-{sensor}"] = dict.copy(SENSORS[sensor])
            template["components"][f"{
                self.UNIQUE_ID}-{sensor}"]["unique_id"] = f"{self.UNIQUE_ID}-{sensor}"

        client.publish(self.BASE_TOPIC + "config",
                       json.dumps(template), retain=True)

    def _on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties):
        print(f"Connected with result code {reason_code}")
        client.subscribe(self.COMMAND_TOPIC)
        client.publish(self.AVAILABILITY_TOPIC, "online", 0, True)
        self._ha_discovery(client)

        if not self.worker_thread.is_alive():
            self.worker_thread.start()

    def _on_message(self, client: mqtt.Client, userdata, message: mqtt.MQTTMessage):
        if message.topic == self.COMMAND_TOPIC:
            try:
                msg = json.loads(message.payload)
                if msg["command"] in AVAILABLE_COMMANDS:
                    self.MESSAGE_QUEUE.put(msg)
            except json.JSONDecodeError:
                pass

    def _timer(self):
        while self.mqtt_client.is_connected():
            while not self.worker_queue.empty():
                message = self.worker_queue.get()
                if message["command"] == "sensors_push":
                    self.sensors_data.update(message["arg"])

            self.mqtt_client.publish(self.STATE_TOPIC,
                                     json.dumps(self.sensors_data),
                                     retain=True)
            time.sleep(10)
        pass
