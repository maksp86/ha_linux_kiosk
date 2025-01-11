from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import queue
import os
import time
from threading import Thread, Timer


class ChromeWorker:
    def __init__(self, WORKING_DIRECTORY: str, UNIQUE_ID: str):
        self.working_directory = WORKING_DIRECTORY
        self.unique_id = UNIQUE_ID
        self.message_queue = queue.Queue()

        chrome_options = Options()

        chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument("--kiosk")
        chrome_options.add_argument("--allow-profiles-outside-user-dir")
        chrome_options.add_argument(
            f"--user-data-dir={os.path.join(self.working_directory, "driver_data")}")
        chrome_options.add_argument("--profile-directory=kiosk_profile")

        self.chrome_options = chrome_options
        self.terminate = False

        self.worker_thread = Thread(
            target=self._thread, name="chrome_thread")

    def start(self):
        self.terminate = False

        self.worker_thread.start()

    def stop(self):
        if self.terminate:
            return
        self.terminate = True

    def push_command(self, message):
        self.message_queue.put(message)

    def _thread(self):
        try:
            print(self.worker_thread.name, "thread started")

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
                if len(self.driver.window_handles) > 1:
                    for handle in [handle for handle in self.driver.window_handles if handle != self.ha_tab]:
                        self.driver.switch_to.window(handle)
                        self.driver.close()

                if not self.message_queue.empty():
                    message = self.message_queue.get(False)

                    match message["command"]:
                        case "reload":
                            self.driver.refresh()

                time.sleep(0.5)

            while len(self.driver.window_handles) > 0:
                self.driver.close()

            print(self.worker_thread.name, "thread stopped")
        except Exception as e:
            print("fatal exception in thread", self.worker_thread.name)
            print(e)
