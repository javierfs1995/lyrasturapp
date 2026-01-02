import numpy as np
import time

from camera.base_camera import BaseCameraManager


class SimulatedCameraManager(BaseCameraManager):
    def __init__(self):
        self.running = False
        self.gain = 0
        self.exposure = 0

    def start_live(self):
        print("[SimulatedCamera] start_live()")
        self.running = True

    def stop_live(self):
        print("[SimulatedCamera] stop_live()")
        self.running = False

    def get_frame(self):
        if not self.running:
            return None

        # Frame simulado (ruido + estrella)
        frame = np.random.normal(20, 5, (480, 640)).astype(np.uint8)
        frame[240, 320] = 255  # estrella brillante en el centro
        time.sleep(0.05)
        return frame

    def set_gain(self, value: int):
        self.gain = value
        print(f"[SimulatedCamera] set_gain({value})")

    def set_exposure(self, ms: float):
        self.exposure = ms
        print(f"[SimulatedCamera] set_exposure({ms})")

    def set_roi(self, x, y, w, h):
        print(f"[SimulatedCamera] set_roi(x={x}, y={y}, w={w}, h={h})")
