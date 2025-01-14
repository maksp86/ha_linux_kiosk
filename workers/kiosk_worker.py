from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import queue
import os
import time
import logging
from threading import Thread
from tkinter import font
import ttkbootstrap as ttk
from sdbus_block.networkmanager import DeviceState


class UICompositor:
    def __init__(self, working_directory: str, uid: str):
        self.ui_worker = UIWorker()
        self.chrome_worker = ChromeWorker(working_directory, uid)
        self.ifstate = None
        self.current_worker = None

    def push_command(self, command):
        if command["command"] == "exit":
            self.chrome_worker.stop()
            self.ui_worker.stop()
        elif command["command"] == "if_state":
            dev_state = DeviceState(command["arg"]["state"])

            label_text = ""
            progress_visibility = False

            match dev_state:
                case DeviceState.ACTIVATED:
                    label_text = f"Connected to {command["arg"]["name"]}"
                    progress_visibility = False
                case DeviceState.PREPARE | DeviceState.CONFIG | DeviceState.IP_CONFIG | DeviceState.IP_CHECK:
                    label_text = f"Connecting to {command["arg"]["name"]}"
                    progress_visibility = True
                case DeviceState.DEACTIVATING | DeviceState.DISCONNECTED:
                    label_text = "Disconnected"
                    progress_visibility = False
                case _:
                    label_text = f"Connection state: {dev_state.name.lower()}"
                    progress_visibility = False

            self.ui_worker.push_command(
                {"command": "ui_update_status_text",
                            "arg": label_text
                 })
            self.ui_worker.push_command(
                {"command": "ui_progress_bar_visibility",
                    "arg": progress_visibility})

            new_state = dev_state is DeviceState.ACTIVATED

            if self.ifstate != new_state:
                self.ifstate = new_state
                if self.current_worker == self.chrome_worker:
                    self.current_worker.stop()

                if new_state:
                    self.current_worker = self.chrome_worker
                else:
                    self.current_worker = self.ui_worker

                self.current_worker.start()
        elif self.current_worker is not None:
            self.current_worker.push_command(command)


class UIWorker:
    def __init__(self):
        self.terminate = None
        self.spawn_window = False
        self.worker_thread = None
        self.worker_queue = queue.Queue()
        pass

    def start(self):
        if self.terminate == False:
            return
        self.terminate = False
        self.spawn_window = True
        self.worker_thread = Thread(target=self._thread,
                                    name="UI_thread")
        self.worker_thread.start()

    def stop(self):
        if self.terminate:
            return
        self.terminate = True

    def push_command(self, command):
        self.worker_queue.put(command)

    def _init_window(self):
        window_size = list(map(int, os.getenv("WINDOW_SIZE").split(",")))

        self.window = ttk.Window(themename="darkly",
                                 position=(0, 0),
                                 size=(window_size),
                                 resizable=(False, False),
                                 overrideredirect=True)

        fontObj = font.Font(size=24, weight="bold")

        self.status_label = ttk.Label(
            self.window, text="Connecting", justify="center",
            font=fontObj,
            wraplength=window_size[0])

        self.status_label.place(width=window_size[0])
        self.status_label.pack(expand=True)

        self.status_progress_bar = ttk.Floodgauge(self.window,
                                                  mode="indeterminate",
                                                  orient="horizontal",
                                                  bootstyle="dark")
        self.status_progress_bar.place_forget()
        self.status_progress_bar.start()

    def _thread(self):
        self._init_window()
        while not self.terminate:
            time.sleep(0.1)
            if not self.worker_queue.empty():
                message = self.worker_queue.get()
                if message["command"] == "ui_update_status_text":
                    self.status_label["text"] = message["arg"]
                elif message["command"] == "ui_progress_bar_visibility":
                    if message["arg"]:
                        self.status_progress_bar.place(rely=0.8, relx=0.5,
                                                       width=self.window.winfo_width() // 3,
                                                       anchor="center")
                    else:
                        self.status_progress_bar.place_forget()

            self.window.update_idletasks()
            self.window.update()
        self.window.quit()


class ChromeWorker:
    def __init__(self, WORKING_DIRECTORY: str, UNIQUE_ID: str):
        self._logger = logging.getLogger("ChromeWorker")

        self.working_directory = WORKING_DIRECTORY
        self.unique_id = UNIQUE_ID
        self.message_queue = queue.Queue()

        chrome_options = Options()

        chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument('--window-position=0,0')
        chrome_options.add_argument(
            f'--window-size={os.getenv("WINDOW_SIZE", "1280,720")}')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument("--kiosk")
        chrome_options.add_argument("--allow-profiles-outside-user-dir")
        chrome_options.add_argument(
            f"--user-data-dir={os.path.join(self.working_directory,
                                            "driver_data")}")
        chrome_options.add_argument("--profile-directory=kiosk_profile")

        self.chrome_options = chrome_options
        self.terminate = False

        self.worker_thread = None

    def start(self):
        self.terminate = False
        self.worker_thread = Thread(
            target=self._thread, name="chrome_thread")

        self.worker_thread.start()

        self._logger.info("started")

    def stop(self):
        if self.terminate:
            return
        self.terminate = True

        self._logger.info("stop requested")

    def push_command(self, message):
        self.message_queue.put(message)

    def _thread(self):
        try:
            self._logger.info("%s thread started", self.worker_thread.name)

            self.driver = webdriver.Chrome(options=self.chrome_options)
            wait = WebDriverWait(self.driver, 20)

            self.driver.get(os.getenv("HA_URL"))

            self.ha_tab = self.driver.current_window_handle

            if self.driver.current_url.count("auth/authorize"):
                wait.until(EC.presence_of_element_located(
                    (By.TAG_NAME, "ha-authorize")))
                login_input = self.driver.find_element(By.NAME, "username")
                login_input.clear()
                login_input.send_keys(os.getenv("HA_LOGIN"))

                password_input = self.driver.find_element(By.NAME, "password")
                password_input.clear()
                password_input.send_keys(os.getenv("HA_PASSWORD"))

                login_button = self.driver.find_element(
                    By.CSS_SELECTOR, ".action>mwc-button")
                login_button.click()

            wait.until(EC.presence_of_element_located(
                (By.TAG_NAME, "home-assistant")))
            webdriver.ActionChains(self.driver).send_keys(
                Keys.ESCAPE).perform()

            while not self.terminate:
                time.sleep(0.5)
                if len(self.driver.window_handles) > 1:
                    for handle in [handle
                                   for handle in self.driver.window_handles
                                   if handle != self.ha_tab]:
                        self.driver.switch_to.window(handle)
                        self.driver.close()

                if not self.message_queue.empty():
                    message = self.message_queue.get(False)

                    match message["command"]:
                        case "reload":
                            self.driver.refresh()

            self.driver.quit()

            self._logger.info("%s thread stopped", self.worker_thread.name)
        except Exception:
            self._logger.exception("%s fatal exception in thread",
                                   self.worker_thread.name, exc_info=True)
