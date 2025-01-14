import queue
import os
import time
import psutil
import logging

import sdbus
from sdbus_block.networkmanager import (
    NetworkManager,
    NetworkDeviceGeneric,
    DeviceState,
    DeviceType,
    DeviceCapabilities as Capabilities,
    ActiveConnection,
    ConnectivityState,
)
from threading import Thread, RLock


class SystemWorker:
    def __init__(self, MESSAGE_QUEUE: queue.Queue):
        self._logger = logging.getLogger("SystemWorker")

        self.message_queue = MESSAGE_QUEUE

        self.worker_queue = queue.Queue()
        self.worker_thread = Thread(target=self._thread, name="system_thread")
        self.worker_timer = Thread(target=self._timer, name="system_timer")
        self.terminate = False
        self.send_message_counter = 0
        self.last_dev_state = 0

        self.sdbus = sdbus.sd_bus_open_system()

    def _get_iface_state(self):

        nm = NetworkManager(self.sdbus)
        path = nm.get_device_by_ip_iface(os.getenv("IFNAME"))
        self.network_dev = NetworkDeviceGeneric(path, self.sdbus)

        active_connection = ""
        if not self.network_dev.active_connection == "/":
            active_connection = ActiveConnection(
                self.network_dev.active_connection, self.sdbus).id

        state = {
            "state": self.network_dev.state,
            "name": active_connection
        }
        return state

    def _get_uptime(self) -> int:
        return int(time.time() - psutil.boot_time())

    def _get_brightness(self) -> int:
        return int(open("/sys/class/backlight/intel_backlight/brightness",
                        "r").read())

    def _set_brightness(self, value: int):
        if value <= 100 and value >= 0:
            open("/sys/class/backlight/intel_backlight/brightness",
                 "w").write(str(value))

    def _get_temperature(self) -> float:
        if psutil.WINDOWS:
            return 0

        temps = psutil.sensors_temperatures()
        return temps["coretemp"][0].current

    def start(self):
        if self.worker_thread.is_alive():
            return

        self.terminate = False

        self.worker_thread.start()

    def stop(self):
        if self.terminate:
            return
        self.terminate = True

    def push_command(self, message):
        self.worker_queue.put(message)

    def _thread(self):
        try:
            self._logger.info("%s thread started", self.worker_thread.name)

            self.worker_timer.start()

            while not self.terminate:
                time.sleep(0.1)
                if self.worker_queue.empty():
                    continue
                message = self.worker_queue.get()

                match message["command"]:
                    case "set_brightness":
                        self._set_brightness(message["arg"])
                    case "reboot":
                        os.system("reboot")
        except Exception:
            self._logger.exception("fatal exception in thread %s",
                                   self.worker_thread.name, exc_info=True)

    def _timer(self):
        while not self.terminate:
            time.sleep(2)
            if self.send_message_counter >= 3:
                sensors_cache = {
                    "cputemp": self._get_temperature(),
                    "brightness": self._get_brightness(),
                    "uptime": self._get_uptime()
                }
                self.message_queue.put(
                    {"command": "sensors_push", "arg": sensors_cache})
                self.send_message_counter = 0
            self.send_message_counter += 1

            new_if_state = self._get_iface_state()

            if new_if_state["state"] != self.last_dev_state:
                self.message_queue.put({
                    "command": "if_state",
                    "arg": new_if_state
                })
                self.last_dev_state = new_if_state["state"]
