import ctypes
import os

from camera.base_camera import BaseCameraManager


class ZWOCameraManager(BaseCameraManager):
    def __init__(self):
        self.sdk = None
        self.camera_connected = False
        self.sdk_available = False
        self._try_load_sdk()

    def _try_load_sdk(self):
        sdk_path = r"C:\Program Files (x86)\ZWO Design\ASI SDK\include\lib\x64\ASICamera2.dll"


        if not os.path.exists(sdk_path):
            print("[ZWO SDK] ASICamera2.dll no encontrada")
            return  # ❗ NO lanzar excepción

        try:
            self.sdk = ctypes.WinDLL(sdk_path)
            self.sdk.ASIGetNumOfConnectedCameras.restype = ctypes.c_int
            num = self.sdk.ASIGetNumOfConnectedCameras()

            self.sdk_available = True
            self.camera_connected = num > 0
            print(f"[ZWO SDK] SDK cargado. Cámaras detectadas: {num}")

        except Exception as e:
            print(f"[ZWO SDK] Error cargando SDK: {e}")

    # ─────────────────────────────
    # API
    # ─────────────────────────────
    def start_live(self):
        if not self.sdk_available:
            print("[ZWO] SDK no disponible → start_live ignorado")
            return
        if not self.camera_connected:
            print("[ZWO] start_live(): no hay cámara")
            return

        print("[ZWO] start_live()")

    def stop_live(self):
        if not self.sdk_available or not self.camera_connected:
            return

        print("[ZWO] stop_live()")

    def get_frame(self):
        if not self.sdk_available or not self.camera_connected:
            return None

        return None  # aquí irá ASIGetVideoData

    def set_gain(self, value: int):
        if not self.sdk_available:
            print(f"[ZWO] set_gain({value}) ignorado (SDK no disponible)")
            return

        print(f"[ZWO] set_gain({value})")

    def set_exposure(self, ms: float):
        if not self.sdk_available:
            print(f"[ZWO] set_exposure({ms}) ignorado (SDK no disponible)")
            return

        print(f"[ZWO] set_exposure({ms})")

    def set_roi(self, x, y, w, h):
        if not self.sdk_available:
            print("[ZWO] set_roi ignorado (SDK no disponible)")
            return

        print(f"[ZWO] set_roi(x={x}, y={y}, w={w}, h={h})")
