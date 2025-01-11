import queue
import os
import time
import psutil
from threading import Thread, RLock


class SystemWorker:
    def __init__(self, MESSAGE_QUEUE: queue.Queue):
        self.message_queue = MESSAGE_QUEUE

        self.worker_queue = queue.Queue()
        self.worker_thread = Thread(target=self._thread, name="system_thread")
        self.worker_timer = Thread(target=self._timer, name="system_timer")
        self.terminate = False
        self.lock = RLock()

    def _get_brightness(self) -> int:
        return int(open("/sys/class/backlight/intel_backlight/brightness", "r").read())

    def _set_brightness(self, value: int):
        if value <= 100 and value >= 0:
            open("/sys/class/backlight/intel_backlight/brightness", "w").write(str(value))

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
            print(self.worker_thread.name, "thread started")

            self.worker_timer.start()

            while not self.terminate:
                if self.worker_queue.empty():
                    continue
                message = self.worker_queue.get()

                match message["command"]:
                    case "set_brightness":
                        self._set_brightness(message["arg"])
                    case "reboot":
                        os.system("reboot")
        except Exception as e:
            print("fatal exception in thread", self.worker_thread.name)
            print(e)

    def _timer(self):
        while not self.terminate:
            with self.lock:
                sensors_cache = {
                    "cputemp": self._get_temperature(),
                    "brightness": self._get_brightness()
                }
                self.message_queue.put(
                    {"command": "sensors_push", "arg": sensors_cache})
            time.sleep(5)
