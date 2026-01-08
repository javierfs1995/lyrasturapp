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

            if writer is None:
                h, w = frame.shape[:2]
                writer = SERWriter(
                    path=path,
                    width=w,
                    height=h,
                    color=False,
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

            if frame.ndim == 2:
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
