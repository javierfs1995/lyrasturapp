import ctypes
import os
import threading
import time

from PySide6.QtGui import QImage
from camera.base_camera import BaseCameraManager


class ZWOCameraManager(BaseCameraManager):
    def __init__(self):
        super().__init__()

        self.sdk = None
        self.camera_connected = False
        self.sdk_available = False

        self._running = False
        self._thread = None

        self._try_load_sdk()

    # ─────────────────────────────
    def _try_load_sdk(self):
        sdk_path = r"C:\Program Files (x86)\ZWO Design\ASI SDK\include\lib\x64\ASICamera2.dll"

        if not os.path.exists(sdk_path):
            print("[ZWO SDK] ASICamera2.dll no encontrada")
            return

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
    # API pública
    # ─────────────────────────────
    def start_live(self):
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

        print("[ZWO] Live View iniciado")

    def stop_live(self):
        self._running = False
        print("[ZWO] Live View detenido")

    # ─────────────────────────────
    def _loop(self):
        if not self.sdk_available or not self.camera_connected:
            self._simulator_loop()
            return

        # ⚠️ De momento seguimos en simulador
        # cuando conectemos ASIGetVideoData aquí entrará el real
        self._simulator_loop()

    # ─────────────────────────────
    def _simulator_loop(self):
        """
        Simulador: permite desarrollar TODA la UI y el overlay
        aunque no haya frame real todavía.
        """
        while self._running:
            img = QImage(1280, 720, QImage.Format_RGB32)
            img.fill(0xFF0B0D10)  # fondo oscuro tipo NINA

            self.frame_ready.emit(img)
            time.sleep(0.2)

    # ─────────────────────────────
    # Controles (ya los tienes, intactos)
    # ─────────────────────────────
    def set_gain(self, value: int):
        if not self.sdk_available:
            print(f"[ZWO] set_gain({value}) ignorado")
            return
        print(f"[ZWO] set_gain({value})")

    def set_exposure(self, ms: float):
        if not self.sdk_available:
            print(f"[ZWO] set_exposure({ms}) ignorado")
            return
        print(f"[ZWO] set_exposure({ms})")

    def set_roi(self, x, y, w, h):
        if not self.sdk_available:
            print("[ZWO] set_roi ignorado")
            return
        print(f"[ZWO] set_roi(x={x}, y={y}, w={w}, h={h})")
