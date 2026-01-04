from __future__ import annotations
import ctypes
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from camera.base_camera import BaseCameraManager


# ─────────────────────────────────────────────
# ZWO SDK ctypes definitions (mínimo viable)
# ─────────────────────────────────────────────

ASI_BOOL = ctypes.c_int
ASI_CAMERA_ID = ctypes.c_int
ASI_ERROR_CODE = ctypes.c_int
ASI_IMG_TYPE = ctypes.c_int
ASI_CONTROL_TYPE = ctypes.c_int

ASI_SUCCESS = 0

# Imagen: usaremos RAW8 para simplificar
ASI_IMG_RAW8 = 0

# Controles típicos
ASI_GAIN = 0
ASI_EXPOSURE = 1

ASI_FALSE = 0
ASI_TRUE = 1


class ASICameraInfo(ctypes.Structure):
    _fields_ = [
        ("Name", ctypes.c_char * 64),
        ("CameraID", ctypes.c_int),
        ("MaxHeight", ctypes.c_long),
        ("MaxWidth", ctypes.c_long),
        ("IsColorCam", ctypes.c_int),
        ("BayerPattern", ctypes.c_int),
        ("SupportedBins", ctypes.c_int * 16),
        ("SupportedVideoFormat", ctypes.c_int * 8),
        ("PixelSize", ctypes.c_double),
        ("MechanicalShutter", ctypes.c_int),
        ("ST4Port", ctypes.c_int),
        ("IsCoolerCam", ctypes.c_int),
        ("IsUSB3Host", ctypes.c_int),
        ("IsUSB3Camera", ctypes.c_int),
        ("ElecPerADU", ctypes.c_float),
        ("BitDepth", ctypes.c_int),
        ("IsTriggerCam", ctypes.c_int),
        ("Unused", ctypes.c_char * 16),
    ]


@dataclass
class _ROI:
    x: int
    y: int
    w: int
    h: int
    bin: int = 1
    img_type: int = ASI_IMG_RAW8


class ZWOCameraManager(BaseCameraManager):
    def __init__(self, dll_path: Optional[str] = None):
        super().__init__()

        self.sdk = None
        self.camera_id: Optional[int] = None
        self.info: Optional[ASICameraInfo] = None

        self._roi = _ROI(0, 0, 0, 0, 1, ASI_IMG_RAW8)
        self._frame_buf = None  # ctypes buffer
        self._frame_bytes = 0

        self._gain = 100
        self._exp_us = 30000  # microsegundos

        self._dll_path = dll_path or r"C:\Program Files (x86)\ZWO Design\ASI SDK\include\lib\x64\ASICamera2.dll"
        self._try_load_sdk()

    def _try_load_sdk(self):
        if not os.path.exists(self._dll_path):
            print("[ZWO SDK] ASICamera2.dll no encontrada:", self._dll_path)
            self.sdk_available = False
            self.camera_connected = False
            return

        try:
            self.sdk = ctypes.WinDLL(self._dll_path)
            self._bind_functions()

            num = self.sdk.ASIGetNumOfConnectedCameras()
            self.sdk_available = True
            self.camera_connected = num > 0
            print(f"[ZWO SDK] SDK cargado. Cámaras detectadas: {num}")

            if self.camera_connected:
                # abrir primera cámara
                self._open_first_camera()

        except Exception as e:
            print(f"[ZWO SDK] Error cargando SDK: {e}")
            self.sdk_available = False
            self.camera_connected = False

    def _bind_functions(self):
        # int ASIGetNumOfConnectedCameras()
        self.sdk.ASIGetNumOfConnectedCameras.restype = ctypes.c_int

        # ASIGetCameraProperty(ASICameraInfo*, int index)
        self.sdk.ASIGetCameraProperty.argtypes = [ctypes.POINTER(ASICameraInfo), ctypes.c_int]
        self.sdk.ASIGetCameraProperty.restype = ASI_ERROR_CODE

        # ASIOpenCamera(int id)
        self.sdk.ASIOpenCamera.argtypes = [ctypes.c_int]
        self.sdk.ASIOpenCamera.restype = ASI_ERROR_CODE

        # ASICloseCamera(int id)
        self.sdk.ASICloseCamera.argtypes = [ctypes.c_int]
        self.sdk.ASICloseCamera.restype = ASI_ERROR_CODE

        # ASIInitCamera(int id)
        self.sdk.ASIInitCamera.argtypes = [ctypes.c_int]
        self.sdk.ASIInitCamera.restype = ASI_ERROR_CODE

        # ASISetROIFormat(int id, int width, int height, int bin, ASI_IMG_TYPE type)
        self.sdk.ASISetROIFormat.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ASI_IMG_TYPE]
        self.sdk.ASISetROIFormat.restype = ASI_ERROR_CODE

        # ASISetStartPos(int id, int x, int y)
        self.sdk.ASISetStartPos.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.sdk.ASISetStartPos.restype = ASI_ERROR_CODE

        # ASIStartVideoCapture(int id)
        self.sdk.ASIStartVideoCapture.argtypes = [ctypes.c_int]
        self.sdk.ASIStartVideoCapture.restype = ASI_ERROR_CODE

        # ASIStopVideoCapture(int id)
        self.sdk.ASIStopVideoCapture.argtypes = [ctypes.c_int]
        self.sdk.ASIStopVideoCapture.restype = ASI_ERROR_CODE

        # ASIGetVideoData(int id, unsigned char* buf, long size, int timeout_ms)
        self.sdk.ASIGetVideoData.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_long, ctypes.c_int]
        self.sdk.ASIGetVideoData.restype = ASI_ERROR_CODE

        # ASISetControlValue(int id, ASI_CONTROL_TYPE, long value, ASI_BOOL auto)
        self.sdk.ASISetControlValue.argtypes = [ctypes.c_int, ASI_CONTROL_TYPE, ctypes.c_long, ASI_BOOL]
        self.sdk.ASISetControlValue.restype = ASI_ERROR_CODE

    def _open_first_camera(self):
        info = ASICameraInfo()
        err = self.sdk.ASIGetCameraProperty(ctypes.byref(info), 0)
        if err != ASI_SUCCESS:
            print("[ZWO] ASIGetCameraProperty error:", err)
            self.camera_connected = False
            return

        cam_id = int(info.CameraID)

        if self.sdk.ASIOpenCamera(cam_id) != ASI_SUCCESS:
            print("[ZWO] ASIOpenCamera falló")
            self.camera_connected = False
            return

        if self.sdk.ASIInitCamera(cam_id) != ASI_SUCCESS:
            print("[ZWO] ASIInitCamera falló")
            self.sdk.ASICloseCamera(cam_id)
            self.camera_connected = False
            return

        self.camera_id = cam_id
        self.info = info

        max_w = int(info.MaxWidth)
        max_h = int(info.MaxHeight)

        # ROI inicial: full frame RAW8
        self._roi = _ROI(0, 0, max_w, max_h, 1, ASI_IMG_RAW8)
        self._alloc_buffer()

        # set controles básicos
        self.set_gain(self._gain)
        self.set_exposure(self._exp_us / 1000.0)

        print(f"[ZWO] Cámara abierta: id={cam_id} {info.Name.decode(errors='ignore')} {max_w}x{max_h}")

    def _alloc_buffer(self):
        # RAW8 => 1 byte/pixel
        self._frame_bytes = int(self._roi.w * self._roi.h)
        self._frame_buf = (ctypes.c_ubyte * self._frame_bytes)()

    def get_sensor_size(self) -> Tuple[int, int]:
        if self.info is None:
            return (1280, 720)
        return (int(self.info.MaxWidth), int(self.info.MaxHeight))

    def set_roi(self, x: int, y: int, w: int, h: int):
        if not self.sdk_available or not self.camera_connected or self.camera_id is None or self.info is None:
            return

        max_w, max_h = self.get_sensor_size()

        x = max(0, min(int(x), max_w - 1))
        y = max(0, min(int(y), max_h - 1))
        w = max(16, min(int(w), max_w - x))
        h = max(16, min(int(h), max_h - y))

        # detener live si está
        was_live = self.is_live
        if was_live:
            self.stop_live()

        self._roi = _ROI(x, y, w, h, 1, ASI_IMG_RAW8)

        # aplicar ROI al SDK
        err1 = self.sdk.ASISetROIFormat(self.camera_id, self._roi.w, self._roi.h, self._roi.bin, self._roi.img_type)
        err2 = self.sdk.ASISetStartPos(self.camera_id, self._roi.x, self._roi.y)

        if err1 != ASI_SUCCESS or err2 != ASI_SUCCESS:
            print("[ZWO] set_roi error:", err1, err2)

        self._alloc_buffer()

        if was_live:
            self.start_live()

    def set_gain(self, value: int):
        self._gain = int(value)
        if not self.sdk_available or not self.camera_connected or self.camera_id is None:
            return
        # auto = False
        self.sdk.ASISetControlValue(self.camera_id, ASI_GAIN, ctypes.c_long(self._gain), ASI_FALSE)

    def set_exposure(self, ms: float):
        # ZWO exposure en microsegundos
        us = int(float(ms) * 1000.0)
        self._exp_us = us
        if not self.sdk_available or not self.camera_connected or self.camera_id is None:
            return
        self.sdk.ASISetControlValue(self.camera_id, ASI_EXPOSURE, ctypes.c_long(self._exp_us), ASI_FALSE)

    def start_live(self) -> bool:
        if not self.sdk_available or not self.camera_connected or self.camera_id is None:
            print("[ZWO] start_live ignorado (sin cámara)")
            self.is_live = False
            return False

        # asegurar ROI actual aplicado (por si acaso)
        self.sdk.ASISetROIFormat(self.camera_id, self._roi.w, self._roi.h, self._roi.bin, self._roi.img_type)
        self.sdk.ASISetStartPos(self.camera_id, self._roi.x, self._roi.y)

        err = self.sdk.ASIStartVideoCapture(self.camera_id)
        if err != ASI_SUCCESS:
            print("[ZWO] ASIStartVideoCapture error:", err)
            self.is_live = False
            return False

        self.is_live = True
        return True

    def stop_live(self) -> None:
        if not self.sdk_available or not self.camera_connected or self.camera_id is None:
            self.is_live = False
            return

        self.sdk.ASIStopVideoCapture(self.camera_id)
        self.is_live = False

    def get_frame(self, timeout_ms: int = 200) -> Optional[np.ndarray]:
        if not self.is_live:
            return None
        if not self.sdk_available or not self.camera_connected or self.camera_id is None:
            return None
        if self._frame_buf is None:
            return None

        err = self.sdk.ASIGetVideoData(
            self.camera_id,
            ctypes.cast(self._frame_buf, ctypes.POINTER(ctypes.c_ubyte)),
            ctypes.c_long(self._frame_bytes),
            int(timeout_ms)
        )
        if err != ASI_SUCCESS:
            return None

        # copiar buffer -> numpy
        # RAW8 -> (H, W) uint8
        arr = np.frombuffer(bytes(self._frame_buf), dtype=np.uint8)
        try:
            img = arr.reshape((self._roi.h, self._roi.w))
        except Exception:
            return None

        return img

    def close(self):
        try:
            if self.sdk_available and self.camera_connected and self.camera_id is not None:
                if self.is_live:
                    self.stop_live()
                self.sdk.ASICloseCamera(self.camera_id)
        except Exception:
            pass
