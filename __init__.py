from threading import Thread
from dotenv import load_dotenv
import os
import psutil
import queue

from workers.mqtt_worker import MQTTWorker
from workers.kiosk_worker import ChromeWorker
from workers.system_worker import SystemWorker


def message_loop(system_worker: SystemWorker, chrome_worker: ChromeWorker, message_queue: queue.Queue):
    while True:
        if message_queue.empty():
            continue
        message = message_queue.get(True)

        match message["command"]:
            case "sensors_push":
                mqtt_worker.push_command(message)
            case "reload":
                chrome_worker.push_command(message)
            case "reboot" | "set_brightness":
                system_worker.push_command(message)
            case "exit":
                os._exit(0)


if __name__ == "__main__":
    load_dotenv()
    WORKING_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

    MAC_ADDR = [psutil.net_if_addrs()[interface][0].address
                for interface in psutil.net_if_addrs()
                if psutil.net_if_addrs()[interface][0].address][0]

    UNIQUE_ID = "kiosk-" + MAC_ADDR.replace('-', '')[-6:].lower()

    MESSAGE_QUEUE = queue.Queue()

    chrome_worker = ChromeWorker(WORKING_DIRECTORY, UNIQUE_ID)
    system_worker = SystemWorker(MESSAGE_QUEUE)
    mqtt_worker = MQTTWorker(UNIQUE_ID, MAC_ADDR, MESSAGE_QUEUE, system_worker)

    mqtt_worker.start()
    chrome_worker.start()
    system_worker.start()

    message_thread = Thread(target=message_loop,
                            kwargs={"system_worker": system_worker,
                                    "chrome_worker": chrome_worker,
                                    "message_queue": MESSAGE_QUEUE},
                            name="message_thread")

    message_thread.start()
