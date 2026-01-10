import time
import os
from datetime import datetime

import numpy as np
from PySide6.QtCore import QObject, Signal

from utils.ser_writer import SERWriter   # 👈 lo creamos después
import cv2


class SequenceWorker(QObject):
    finished = Signal()
    error = Signal(str)
    progress = Signal(int, int)  # actual, total

    def __init__(self, cam, params: dict):
        super().__init__()

        self.cam = cam
        self.params = params
        self._running = True

        self._saved_state = {}

    # ─────────────────────────────────────────────
    # Entry point
    # ─────────────────────────────────────────────

    def run(self):
        try:
            self._save_camera_state()
            self._apply_capture_settings()

            cap_type = self.params["type"]
            captures = self.params["captures"]

            for i in range(captures):
                if not self._running:
                    break

                if cap_type == "SER":
                    self._capture_ser(i + 1)
                elif cap_type == "AVI":
                    self._capture_avi(i + 1)
                elif cap_type == "FITS":
                    self._capture_fits(i + 1)

                self.progress.emit(i + 1, captures)

            self._restore_camera_state()
            self.finished.emit()

        except Exception as e:
            self._restore_camera_state()
            self.error.emit(str(e))

    def stop(self):
        self._running = False

    # ─────────────────────────────────────────────
    # Camera state
    # ─────────────────────────────────────────────

    def _save_camera_state(self):
        self._saved_state = {
            "exposure_ms": getattr(self.cam, "get_exposure", lambda: None)(),
            "gain": getattr(self.cam, "get_gain", lambda: None)(),
            "roi": getattr(self.cam, "get_roi", lambda: None)(),
        }

        try:
            self.cam.stop_live()
        except Exception:
            pass

    def _apply_capture_settings(self):
        exp_ms = self.params["exposure_s"] * 1000.0
        gain = self.params["gain"]

        if hasattr(self.cam, "set_exposure"):
            self.cam.set_exposure(exp_ms)

        if hasattr(self.cam, "set_gain"):
            self.cam.set_gain(gain)

    def _restore_camera_state(self):
        try:
            if self._saved_state.get("exposure_ms") is not None:
                self.cam.set_exposure(self._saved_state["exposure_ms"])
            if self._saved_state.get("gain") is not None:
                self.cam.set_gain(self._saved_state["gain"])
            if self._saved_state.get("roi") is not None:
                self.cam.set_roi(*self._saved_state["roi"])

            self.cam.start_live()
        except Exception:
            pass

    # ─────────────────────────────────────────────
    # SER
    # ─────────────────────────────────────────────

    def _capture_ser(self, index: int):
        duration = self.params["duration_s"]
        out_dir = self.params["output_dir"]

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"capture_{ts}_{index:03d}.ser")

        writer = None

        t0 = time.time()
        frame_count = 0

        while time.time() - t0 < duration and self._running:
            frame = self.cam.capture(self.params["exposure_s"] * 1000.0)

            if frame is None:
                continue

            if self.params.get("color", False):
                frame = self._debayer(frame)
                frame = self._apply_white_balance(frame)

            if writer is None:
                h, w = frame.shape[:2]
                writer = SERWriter(
                    path=path,
                    width=w,
                    height=h,
                    color=True,
                    bit_depth=8,
                    fps=1.0 / self.params["exposure_s"],
                )

            writer.write(frame)
            frame_count += 1

        if writer:
            writer.close()

    # ─────────────────────────────────────────────
    # AVI
    # ─────────────────────────────────────────────

    def _capture_avi(self, index: int):
        duration = self.params["duration_s"]
        out_dir = self.params["output_dir"]

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"capture_{ts}_{index:03d}.avi")

        writer = None
        t0 = time.time()

        while time.time() - t0 < duration and self._running:
            frame = self.cam.capture(self.params["exposure_s"] * 1000.0)

            if frame is None:
                continue

            if writer is None:
                h, w = frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"MJPG")
                writer = cv2.VideoWriter(path, fourcc, 1.0 / self.params["exposure_s"], (w, h), True)

            if self.params.get("color", False):
                frame = self._debayer(frame)
                frame = self._apply_white_balance(frame)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

            writer.write(frame)

        if writer:
            writer.release()

    # ─────────────────────────────────────────────
    # FITS
    # ─────────────────────────────────────────────

    def _capture_fits(self, index: int):
        from astropy.io import fits

        out_dir = self.params["output_dir"]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        path = os.path.join(out_dir, f"capture_{ts}_{index:03d}.fits")

        frame = self.cam.capture(self.params["exposure_s"] * 1000.0)

        if frame is None:
            raise RuntimeError("Frame FITS vacío")

        hdu = fits.PrimaryHDU(frame)
        hdu.header["EXPTIME"] = self.params["exposure_s"]
        hdu.header["GAIN"] = self.params["gain"]
        hdu.writeto(path, overwrite=True)

    def _debayer(self, frame: np.ndarray) -> np.ndarray:
        pattern = self.params.get("bayer", "BGGR")

        bayer_map = {
            "RGGB": cv2.COLOR_BayerRG2RGB,
            "BGGR": cv2.COLOR_BayerBG2RGB,
            "GRBG": cv2.COLOR_BayerGR2RGB,
            "GBRG": cv2.COLOR_BayerGB2RGB,
        }

        code = bayer_map.get(pattern)
        if code is None:
            raise RuntimeError(f"Patrón Bayer no soportado: {pattern}")

        return cv2.cvtColor(frame, code)


    def _apply_white_balance(self, rgb: np.ndarray) -> np.ndarray:
        r = self.params.get("wb_r", 1.0)
        g = self.params.get("wb_g", 1.0)
        b = self.params.get("wb_b", 1.0)

        out = rgb.astype(np.float32)
        out[:, :, 0] *= r
        out[:, :, 1] *= g
        out[:, :, 2] *= b

        return np.clip(out, 0, 255).astype(np.uint8)
