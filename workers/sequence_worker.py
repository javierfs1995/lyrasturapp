import time
import os
import cv2
import numpy as np

from PySide6.QtCore import QObject, Signal


class SequenceWorker(QObject):
    finished = Signal()
    error = Signal(str)
    progress = Signal(int, int)

    def __init__(
        self,
        cam,
        live_service,
        output_dir: str,
        cap_type: str,
        exposure_s: float,
        gain: int,
        duration_s: float | None,
        n_caps: int,
    ):
        super().__init__()

        self.cam = cam
        self.live = live_service
        self.output_dir = output_dir
        self.cap_type = cap_type
        self.exposure_s = exposure_s
        self.gain = gain
        self.duration_s = duration_s
        self.n_caps = n_caps

        self._frames: list[np.ndarray] = []
        self._running = True

    # 🔴 RECIBE FRAMES DEL LIVEVIEW
    def push_frame(self, frame: np.ndarray):
        if not self._running:
            return

        if self.cap_type in ("AVI", "SER"):
            self._frames.append(frame.copy())

    # 🔴 MÉTODO QUE NO ENCONTRABAS
    def run(self):
        try:
            self._save_camera_state()
            self._apply_capture_settings()

            for i in range(self.n_caps):
                if not self._running:
                    break

                if self.cap_type in ("AVI", "SER"):
                    self._capture_video_block(i)
                else:
                    self._capture_fits(i)

                self.progress.emit(i + 1, self.n_caps)

            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))

        finally:
            self._restore_camera_state()

    # ─────────────────────────────
    # CAPTURA VIDEO
    # ─────────────────────────────
    def _capture_video_block(self, index: int):
        self._frames.clear()
        t_start = None

        while self._running:
            if self._frames and t_start is None:
                t_start = time.time()

            if t_start and (time.time() - t_start) >= self.duration_s:
                break

            time.sleep(0.005)

        if not self._frames:
            raise RuntimeError("No se capturaron frames")

        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(
            self.output_dir,
            f"seq_{index+1:03d}_{ts}.avi"
        )

        self._save_avi(self._frames, path)

    # ─────────────────────────────
    # FITS
    # ─────────────────────────────
    def _capture_fits(self, index: int):
        time.sleep(self.exposure_s)

        if not self._frames:
            raise RuntimeError("No se recibió frame FITS")

        frame = self._frames[-1]

        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(
            self.output_dir,
            f"seq_{index+1:03d}_{ts}.fits"
        )

        from astropy.io import fits
        fits.writeto(path, frame, overwrite=True)

    # ─────────────────────────────
    # AVI
    # ─────────────────────────────
    def _save_avi(self, frames: list[np.ndarray], path: str, fps: int = 30):
        h, w = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(path, fourcc, fps, (w, h), True)

        if not writer.isOpened():
            raise RuntimeError("No se pudo crear AVI")

        for f in frames:
            if f.ndim == 2:
                f = cv2.cvtColor(f, cv2.COLOR_GRAY2BGR)
            writer.write(f)

        writer.release()

    # ─────────────────────────────
    # ESTADO CÁMARA
    # ─────────────────────────────
    def _save_camera_state(self):
        self._saved_state = {
            "exposure_ms": getattr(self.cam, "_exposure_ms", None),
            "gain": getattr(self.cam, "_gain", None),
            "roi": getattr(self.cam, "_roi", None),
        }

    def _restore_camera_state(self):
        st = getattr(self, "_saved_state", None)
        if not st:
            return

        try:
            if st["exposure_ms"] is not None:
                self.cam.set_exposure(st["exposure_ms"])
            if st["gain"] is not None:
                self.cam.set_gain(st["gain"])
            if st["roi"] is not None:
                x, y, w, h = st["roi"]
                self.cam.set_roi(x, y, w, h)
        except Exception:
            pass

    def _apply_capture_settings(self):
        if hasattr(self.cam, "set_exposure"):
            self.cam.set_exposure(self.exposure_s * 1000.0)
        if hasattr(self.cam, "set_gain"):
            self.cam.set_gain(self.gain)

    def stop(self):
        self._running = False
