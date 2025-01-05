# capturer.py
import threading
import time
import pyautogui
from PIL import Image

class ScreenCapturer:
    """
    A cross-platform screenshot approach using pyautogui.
    """
    def capture(self):
        """
        Returns (bits, width, height) in RGBA format.
        """
        # Grab a screenshot as a Pillow Image in RGB mode
        img = pyautogui.screenshot()

        # Convert to RGBA to keep it consistent
        img = img.convert("RGBA")
        width, height = img.size

        # Convert the image to raw RGBA bytes
        bits = img.tobytes("raw", "RGBA")

        return bits, width, height

class RecentScreen:
    """
    Continuously refreshes a screenshot in the background
    so the rest of the code can grab the "latest" screen data.
    """
    def __init__(self, capture_interval=0.1):
        self.capturer = ScreenCapturer()
        self.screenshot = self.capturer.capture()  # (bits, w, h)
        self.capture_interval = capture_interval
        self.lock = threading.Lock()

        # Start a background thread to periodically update the screenshot
        self.refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self.refresh_thread.start()

    def _refresh_loop(self):
        while True:
            shot = self.capturer.capture()
            with self.lock:
                self.screenshot = shot
            time.sleep(self.capture_interval)

    def get(self):
        """Safely retrieve the current (bits, width, height)."""
        with self.lock:
            return self.screenshot
