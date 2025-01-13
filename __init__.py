from threading import Thread
from dotenv import load_dotenv
import os
import queue
import psutil
import logging
import json

from workers.mqtt_worker import MQTTWorker
from workers.kiosk_worker import ChromeWorker
from workers.system_worker import SystemWorker

logging.basicConfig(filename="kiosk.log",
                    filemode='a',
                    format='%(asctime)s - (%(levelname)s) [%(name)s]: %(message)s',
                    datefmt='%d-%m-%Y %H:%M:%S',
                    level=logging.INFO)

_logger = logging.getLogger("main_thread")


def get_mac_by_name(ifname: str):
    addrs = psutil.net_if_addrs()
    if ifname not in addrs:
        raise Exception("Interface not found, check configuration!")
    for addr in addrs[ifname]:
        if addr.family.name == "AF_LINK" or addr.family.name == "AF_PACKET":
            return addr.address.replace("-", ":")


def message_loop(system_worker: SystemWorker, chrome_worker: ChromeWorker,
                 mqtt_worker: MQTTWorker, message_queue: queue.Queue):
    while True:
        if message_queue.empty():
            continue
        message = message_queue.get(True)

        _logger.debug("New message %s", json.dumps(message))

        match message["command"]:
            case "sensors_push":
                mqtt_worker.push_command(message)
            case "reload":
                chrome_worker.push_command(message)
            case "reboot" | "set_brightness":
                system_worker.push_command(message)
            case "exit":
                system_worker.stop()
                chrome_worker.stop()
                mqtt_worker.stop()
                exit()


if __name__ == "__main__":
    load_dotenv()

    _logger.info("Starting")
    _logger.info("ENV: %s", os.environ)

    WORKING_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

    MAC_ADDR = get_mac_by_name(os.getenv("IFNAME"))

    UNIQUE_ID = "kiosk-" + MAC_ADDR.replace(':', '')[-6:].lower()

    MESSAGE_QUEUE = queue.Queue()

    chrome_worker = ChromeWorker(WORKING_DIRECTORY, UNIQUE_ID)
    system_worker = SystemWorker(MESSAGE_QUEUE)
    mqtt_worker = MQTTWorker(UNIQUE_ID, MAC_ADDR, MESSAGE_QUEUE, system_worker)

    mqtt_worker.start()
    # chrome_worker.start()
    system_worker.start()

    message_thread = Thread(target=message_loop,
                            kwargs={"system_worker": system_worker,
                                    "chrome_worker": chrome_worker,
                                    "mqtt_worker": mqtt_worker,
                                    "message_queue": MESSAGE_QUEUE},
                            name="message_thread")

    message_thread.start()
