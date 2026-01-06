# ui/camera_page.py
# CameraPage (NINA-ish shell + FireCapture-ish LiveView)
# - NO depende de fps kw en LiveViewService.start()
# - NO usa FrameBus.instance()
# - Si no hay ZWO, usa simulador sin crashear
# - Live View con overlay, zoom, ROI, histograma, proyector
# - 🆕 Captura dedicada con Live View activo (MODELO B)

from __future__ import annotations

import time
import math
import os
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QRect, QSize, QPoint, QThread
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSpinBox, QDoubleSpinBox, QCheckBox, QSlider, QSplitter,
    QSizePolicy, QMessageBox, QGroupBox, QGridLayout
)

try:
    from camera.zwo_camera import ZWOCameraManager
except Exception:
    ZWOCameraManager = None


def _get_frame_bus():
    try:
        from camera.frame_bus import FrameBus
        return FrameBus()
    except Exception:
        return None


try:
    from LIVE_VIEW_PROJECTOR import LiveViewProjector
except Exception:
    LiveViewProjector = None


def _qimage_from_ndarray(frame: np.ndarray) -> QImage:
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        return QImage()

    arr = np.ascontiguousarray(frame)

    if arr.dtype != np.uint8:
        a = arr.astype(np.float32)
        a -= float(np.min(a)) if a.size else 0.0
        mx = float(np.max(a)) if a.size else 1.0
        a = (a / max(mx, 1e-6)) * 255.0
        arr = np.clip(a, 0, 255).astype(np.uint8)

    if arr.ndim == 2:
        h, w = arr.shape
        return QImage(arr.data, w, h, w, QImage.Format_Grayscale8).copy()

    if arr.ndim == 3 and arr.shape[2] == 3:
        h, w, _ = arr.shape
        return QImage(arr.data, w, h, w * 3, QImage.Format_RGB888).copy()

    return QImage()


def _clamp(v: int, a: int, b: int) -> int:
    return max(a, min(b, v))


class SimulatedCameraManager:
    def __init__(self):
        self.sdk_available = False
        self.camera_connected = False
        self._t0 = time.time()
        self._gain = 120
        self._exposure_ms = 20.0
        self._roi = None
        self._w = 1280
        self._h = 720

    def start_live(self): return True
    def stop_live(self): return True
    def set_gain(self, v: int): self._gain = int(v)
    def set_exposure(self, ms: float): self._exposure_ms = float(ms)
    def set_roi(self, x, y, w, h): self._roi = (x, y, w, h)

    def get_frame(self):
        w, h = self._w, self._h
        img = np.random.normal(10, 6, (h, w)).astype(np.float32)

        xs = np.random.randint(0, w, 250)
        ys = np.random.randint(0, h, 250)
        img[ys, xs] += np.random.uniform(120, 220, 250)

        t = time.time() - self._t0
        cx = w * 0.52 + math.sin(t * 0.35) * 20
        cy = h * 0.48 + math.cos(t * 0.28) * 12

        for yy in range(int(cy - 8), int(cy + 8)):
            for xx in range(int(cx - 8), int(cx + 8)):
                if 0 <= xx < w and 0 <= yy < h:
                    img[yy, xx] += 200

        img *= (0.6 + self._gain / 300.0) * (0.7 + self._exposure_ms / 80.0)
        img = np.clip(img, 0, 255).astype(np.uint8)

        if self._roi:
            x, y, rw, rh = self._roi
            img = img[y:y + rh, x:x + rw]

        return img

    # 🆕 CAPTURA DEDICADA
    def capture(self, exposure_ms: float):
        time.sleep(exposure_ms / 1000.0)
        return self.get_frame()


class LiveViewService(QObject):
    frame_ready = Signal(object)

    def __init__(self, cam, parent=None):
        super().__init__(parent)
        self.cam = cam
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._running = False

    def start(self, fps=12):
        if self._running:
            return True
        self._running = True
        self.cam.start_live()
        self.timer.start(int(1000 / max(1, min(60, int(fps)))))
        return True

    def stop(self):
        if not self._running:
            return True
        self.timer.stop()
        self._running = False
        self.cam.stop_live()
        return True

    def _tick(self):
        try:
            frame = self.cam.get_frame()
            if frame is not None:
                self.frame_ready.emit(frame)
        except Exception:
            pass

# ─────────────────────────────────────────────
# CameraWorker para no bloquear el LiveView
# ─────────────────────────────────────────────

class CaptureWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, cam, exposure_s):
        super().__init__()
        self.cam = cam
        self.exposure_s = exposure_s

    def run(self):
        try:
            # Simulador
            if hasattr(self.cam, "capture"):
                frame = self.cam.capture(self.exposure_s * 1000.0)

            # ZWO REAL (modelo FireCapture)
            else:
                frame = self._zwo_firecapture_like()

            self.finished.emit(frame)

        except Exception as e:
            self.error.emit(str(e))

# ─────────────────────────────────────────────
# VideoCaptureWorker para capturar largas exposiciones
# ─────────────────────────────────────────────

class VideoCaptureWorker(QObject):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, duration_s: float):
        super().__init__()
        self.duration_s = duration_s
        self._frames = []
        self._running = True

    def push_frame(self, frame: np.ndarray):
        if self._running:
            self._frames.append(frame.copy())

    def run(self):
        try:
            t0 = time.time()
            while time.time() - t0 < self.duration_s:
                time.sleep(0.01)
            self._running = False
            self.finished.emit(self._frames)
        except Exception as e:
            self.error.emit(str(e))

# ─────────────────────────────────────────────
# AVISaveWorker para guardar los videos
# ─────────────────────────────────────────────          

class AviSaveWorker(QObject):
    finished = Signal()
    error = Signal(str)

    def __init__(self, frames, path, fps):
        super().__init__()
        self.frames = frames
        self.path = path
        self.fps = fps

    def run(self):
        try:
            h, w = self.frames[0].shape[:2]
            writer = cv2.VideoWriter(
                self.path,
                cv2.VideoWriter_fourcc(*"MJPG"),
                self.fps,
                (w, h),
                True
            )

            if not writer.isOpened():
                raise RuntimeError("No se pudo abrir el writer AVI")

            for f in self.frames:
                if f.ndim == 2:
                    f = cv2.cvtColor(f, cv2.COLOR_GRAY2BGR)
                writer.write(f)

            writer.release()
            self.finished.emit()

        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────
# LiveView Widget (pinta frame + overlay + zoom + pan)
# ─────────────────────────────────────────────
@dataclass
class OverlayOptions:
    crosshair: bool = True
    grid: bool = True
    info: bool = True
    roi: bool = True


class LiveViewWidget(QWidget):
    """
    Renderiza frame con zoom (tipo FireCapture):
      - rueda: zoom in/out
      - doble click: reset a Fit
    Overlay: crosshair, grid, info, ROI rect
    """

    def __init__(self):
        super().__init__()
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._frame: Optional[np.ndarray] = None
        self._pix: Optional[QPixmap] = None

        self.overlay = OverlayOptions()

        self._zoom = 1.0
        self._fit = True
        self._pan = QPoint(0, 0)
        self._last_mouse: Optional[QPoint] = None
        self._roi_rect: Optional[QRect] = None

        self._last_fps_ts = time.time()
        self._fps = 0.0
        self._fps_counter = 0

        self.setMouseTracking(True)

    def set_frame(self, frame: np.ndarray):
        self._frame = frame
        qimg = _qimage_from_ndarray(frame)
        if qimg.isNull():
            return
        self._pix = QPixmap.fromImage(qimg)

        # FPS calc
        self._fps_counter += 1
        now = time.time()
        if (now - self._last_fps_ts) >= 0.8:
            self._fps = self._fps_counter / (now - self._last_fps_ts)
            self._fps_counter = 0
            self._last_fps_ts = now

        self.update()

    def set_roi_rect(self, rect: Optional[QRect]):
        self._roi_rect = rect
        self.update()

    def set_fit(self, enabled: bool):
        self._fit = bool(enabled)
        if self._fit:
            self._pan = QPoint(0, 0)
        self.update()

    def set_zoom(self, z: float):
        self._zoom = max(0.25, min(8.0, float(z)))
        self._fit = False
        self.update()

    def zoom(self) -> float:
        return self._zoom

    def reset_view(self):
        self._fit = True
        self._zoom = 1.0
        self._pan = QPoint(0, 0)
        self.update()

    def wheelEvent(self, e):
        if self._pix is None:
            return
        delta = e.angleDelta().y()
        if delta == 0:
            return
        factor = 1.12 if delta > 0 else 1 / 1.12
        self.set_zoom(self._zoom * factor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._last_mouse = e.pos()

    def mouseMoveEvent(self, e):
        if self._last_mouse is not None and (e.buttons() & Qt.LeftButton):
            d = e.pos() - self._last_mouse
            self._pan += d
            self._last_mouse = e.pos()
            self._fit = False
            self.update()

    def mouseReleaseEvent(self, e):
        self._last_mouse = None

    def mouseDoubleClickEvent(self, e):
        self.reset_view()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0b0d10"))

        if self._pix is None:
            p.setPen(QColor("#8b95a3"))
            p.setFont(QFont("Segoe UI", 12, QFont.Bold))
            p.drawText(self.rect(), Qt.AlignCenter, "Esperando Live View…")
            return

        vw = self.width()
        vh = self.height()
        iw = self._pix.width()
        ih = self._pix.height()

        if iw <= 0 or ih <= 0:
            return

        # escala
        if self._fit:
            s = min(vw / iw, vh / ih)
        else:
            s = self._zoom

        dw = int(iw * s)
        dh = int(ih * s)

        x = (vw - dw) // 2 + self._pan.x()
        y = (vh - dh) // 2 + self._pan.y()
        target = QRect(x, y, dw, dh)

        p.drawPixmap(target, self._pix)

        p.setRenderHint(QPainter.Antialiasing, True)

        # grid
        if self.overlay.grid:
            p.setPen(QPen(QColor(255, 255, 255, 35), 1))
            for k in (1, 2):
                gx = x + (dw * k) // 3
                gy = y + (dh * k) // 3
                p.drawLine(gx, y, gx, y + dh)
                p.drawLine(x, gy, x + dw, gy)

        # crosshair
        if self.overlay.crosshair:
            p.setPen(QPen(QColor(255, 255, 255, 90), 1))
            cx = x + dw // 2
            cy = y + dh // 2
            p.drawLine(cx, y, cx, y + dh)
            p.drawLine(x, cy, x + dw, cy)

        # ROI
        if self.overlay.roi and self._roi_rect is not None:
            rx = x + int(self._roi_rect.x() * s)
            ry = y + int(self._roi_rect.y() * s)
            rw = int(self._roi_rect.width() * s)
            rh = int(self._roi_rect.height() * s)
            p.setPen(QPen(QColor("#ff9a3d"), 2))
            p.drawRect(QRect(rx, ry, rw, rh))

        # info
        if self.overlay.info:
            p.setPen(QColor("#cfd6dd"))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            txt = f"Zoom: {('Fit' if self._fit else f'{self._zoom:.2f}x')}   FPS: {self._fps:.1f}"
            p.drawText(12, 22, txt)

        # 🆕 overlay captura dedicada (MODELO B)
        parent = self.parent()
        if parent is not None and getattr(parent, "_capture_running", False):
            p.setPen(QColor("#ffcc66"))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            p.drawText(12, 42, "LIVE (preview) — Capturando exposición dedicada")


# ─────────────────────────────────────────────
# Histogram Widget
# ─────────────────────────────────────────────
class HistogramWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(120)
        self._hist = None
        self._min = 0
        self._max = 255

    def set_frame(self, frame: Optional[np.ndarray]):
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            self._hist = None
            self.update()
            return

        g = frame[..., 0] if frame.ndim == 3 else frame

        if g.dtype != np.uint8:
            a = g.astype(np.float32)
            a -= float(np.min(a))
            mx = float(np.max(a)) or 1.0
            g = np.clip((a / mx) * 255.0, 0, 255).astype(np.uint8)

        hist = np.bincount(g.ravel(), minlength=256).astype(np.float32)
        if hist.max() > 0:
            hist /= hist.max()

        self._hist = hist
        self._min = int(g.min())
        self._max = int(g.max())
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#101318"))

        p.setPen(QColor("#23262d"))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

        if self._hist is None:
            p.setPen(QColor("#8b95a3"))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(self.rect(), Qt.AlignCenter, "Histograma —")
            return

        w = self.width()
        h = self.height()

        p.setPen(QPen(QColor(220, 230, 245, 170), 1))
        for i in range(256):
            x = int(i * (w / 256.0))
            v = float(self._hist[i])
            y0 = h - 8
            y1 = int((h - 20) * (1.0 - v))
            p.drawLine(x, y0, x, y1)

        p.setPen(QColor("#8b95a3"))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(8, 16, f"Min {self._min}  Max {self._max}")
# ─────────────────────────────────────────────
# CameraPage
# ─────────────────────────────────────────────
class CameraPage(QWidget):
    """
    Página de cámara (solo esta página estilo FireCapture en el live view).
    Mantiene la shell NINA del MainWindow (QSS global).
    """

    def _get_camera_state(self):
        return {
            "exp": float(self.sp_exp.value()),
            "gain": int(self.sp_gain.value()),
            "roi": self._roi_rect if self._roi_enabled else None,
        }

    def _restore_camera_state(self, state):
        try:
            self.cam_manager.set_exposure(state["exp"])
            self.cam_manager.set_gain(state["gain"])
            if state["roi"] is not None:
                r = state["roi"]
                self.cam_manager.set_roi(r.x(), r.y(), r.width(), r.height())
            else:
                self.cam_manager.set_roi(0, 0, 999999, 999999)
        except Exception:
            pass

    def __init__(self, cam_manager=None):
        super().__init__()

        # Bus (IMPORTANTE: en tu proyecto FrameBus NO tiene .instance())
        self.bus = _get_frame_bus()

        # camera manager: si no hay ZWO o no hay cámara, simulador
        self.no_camera_detected = False
        self.cam_manager = self._init_camera_manager(cam_manager)

        # live service (QTimer en hilo UI)
        self.live = LiveViewService(self.cam_manager, parent=self)
        self.live.frame_ready.connect(self.on_frame)

        # estado ROI
        self._roi_enabled = False
        self._roi_rect = QRect(0, 0, 0, 0)

        # estado captura dedicada
        self._capture_running = False
        self._last_frame: Optional[np.ndarray] = None

        # ───── Estado captura de vídeo (FireCapture style)
        self._video_frames: list[np.ndarray] = []
        self._video_capture_end_ts: float = 0.0


        self._build_ui()
        self._wire_ui()
        self._update_camera_status_label()

    # ─────────────────────────
    def _init_camera_manager(self, cam_manager):
        if cam_manager is not None:
            return cam_manager

        if ZWOCameraManager is not None:
            try:
                z = ZWOCameraManager()
                if getattr(z, "sdk_available", False) and not getattr(z, "camera_connected", False):
                    self.no_camera_detected = True
                    return SimulatedCameraManager()
                if not getattr(z, "sdk_available", False):
                    self.no_camera_detected = True
                    return SimulatedCameraManager()
                return z
            except Exception:
                self.no_camera_detected = True
                return SimulatedCameraManager()

        self.no_camera_detected = True
        return SimulatedCameraManager()

    # ─────────────────────────
    # UI
    # ─────────────────────────

    def _on_capture_done(self, frame: np.ndarray):
        self._capture_running = False

        self.live_view.set_frame(frame)
        self.hist.set_frame(frame)

        self._save_captured_frame(frame)

    def _on_capture_error(self, msg: str):
        self._capture_running = False
        QMessageBox.critical(self, "Error en captura", msg)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # header
        header = QHBoxLayout()
        title = QLabel("📷 Camera")
        title.setStyleSheet("font-size:16px; font-weight:800;")
        header.addWidget(title)
        header.addStretch()

        self.lbl_cam_status = QLabel("—")
        self.lbl_cam_status.setStyleSheet("color:#8b95a3;")
        header.addWidget(self.lbl_cam_status)

        root.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ───── Left panel
        self.left = self._card()
        self.left.setFixedWidth(340)
        l = QVBoxLayout(self.left)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(12)

        # ───── Live View controls
        gb_live = QGroupBox("Live View")
        gb_live.setStyleSheet("QGroupBox{font-weight:700;}")
        gl = QGridLayout(gb_live)
        gl.setContentsMargins(10, 10, 10, 10)
        gl.setHorizontalSpacing(10)
        gl.setVerticalSpacing(8)

        self.btn_start = QPushButton("▶ Iniciar Live")
        self.btn_stop = QPushButton("■ Parar")
        self.btn_stop.setEnabled(False)

        self.btn_project = QPushButton("🖥 Proyectar Live View")
        self.btn_project.setToolTip("Abre el proyector en otra pantalla")

        # 🆕 Captura dedicada
        self.btn_capture_dedicated = QPushButton("📸 Captura dedicada")
        self.btn_capture_dedicated.setToolTip("Captura con exposición dedicada (Live View continúa)")

        gl.addWidget(self.btn_start, 0, 0, 1, 2)
        gl.addWidget(self.btn_stop, 0, 2, 1, 1)
        gl.addWidget(self.btn_project, 1, 0, 1, 3)
        gl.addWidget(self.btn_capture_dedicated, 2, 0, 1, 3)

        l.addWidget(gb_live)

        # ───── Captura dedicada
        gb_cap = QGroupBox("Captura dedicada")
        gb_cap.setStyleSheet("QGroupBox{font-weight:700;}")
        gc = QGridLayout(gb_cap)
        gc.setContentsMargins(10, 10, 10, 10)
        gc.setHorizontalSpacing(10)
        gc.setVerticalSpacing(8)

        gc.addWidget(QLabel("Exposición (s)"), 0, 0)
        self.sp_cap_exp = QDoubleSpinBox()
        self.sp_cap_exp.setRange(0.01, 3600.0)
        self.sp_cap_exp.setDecimals(2)
        self.sp_cap_exp.setValue(5.0)
        self.sp_cap_exp.setSuffix(" s")
        gc.addWidget(self.sp_cap_exp, 0, 1, 1, 2)

        l.addWidget(gb_cap)

        # ───── Exposure / gain
        gb_cam = QGroupBox("Cámara")
        gb_cam.setStyleSheet("QGroupBox{font-weight:700;}")
        gc2 = QGridLayout(gb_cam)
        gc2.setContentsMargins(10, 10, 10, 10)
        gc2.setHorizontalSpacing(10)
        gc2.setVerticalSpacing(8)

        gc2.addWidget(QLabel("Exposición (ms)"), 0, 0)
        self.sp_exp = QDoubleSpinBox()
        self.sp_exp.setRange(0.1, 60000.0)
        self.sp_exp.setValue(20.0)
        self.sp_exp.setSuffix(" ms")
        gc2.addWidget(self.sp_exp, 0, 1, 1, 2)

        gc2.addWidget(QLabel("Ganancia"), 1, 0)
        self.sl_gain = QSlider(Qt.Horizontal)
        self.sl_gain.setRange(0, 300)
        self.sl_gain.setValue(120)
        self.sp_gain = QSpinBox()
        self.sp_gain.setRange(0, 300)
        self.sp_gain.setValue(120)

        gc2.addWidget(self.sl_gain, 1, 1)
        gc2.addWidget(self.sp_gain, 1, 2)

        l.addWidget(gb_cam)

        # ───── ROI
        gb_roi = QGroupBox("ROI")
        gb_roi.setStyleSheet("QGroupBox{font-weight:700;}")
        gr = QGridLayout(gb_roi)

        self.chk_roi = QCheckBox("Activar ROI")
        gr.addWidget(self.chk_roi, 0, 0, 1, 3)

        self.sp_rx = QSpinBox(); self.sp_rx.setRange(0, 99999)
        self.sp_ry = QSpinBox(); self.sp_ry.setRange(0, 99999)
        self.sp_rw = QSpinBox(); self.sp_rw.setRange(16, 99999); self.sp_rw.setValue(640)
        self.sp_rh = QSpinBox(); self.sp_rh.setRange(16, 99999); self.sp_rh.setValue(480)

        gr.addWidget(QLabel("X"), 1, 0); gr.addWidget(self.sp_rx, 1, 1, 1, 2)
        gr.addWidget(QLabel("Y"), 2, 0); gr.addWidget(self.sp_ry, 2, 1, 1, 2)
        gr.addWidget(QLabel("W"), 3, 0); gr.addWidget(self.sp_rw, 3, 1, 1, 2)
        gr.addWidget(QLabel("H"), 4, 0); gr.addWidget(self.sp_rh, 4, 1, 1, 2)

        self.btn_apply_roi = QPushButton("Aplicar ROI")
        gr.addWidget(self.btn_apply_roi, 5, 0, 1, 3)

        l.addWidget(gb_roi)

        # ───── Overlay
        gb_ov = QGroupBox("Overlay")
        gb_ov.setStyleSheet("QGroupBox{font-weight:700;}")
        go = QGridLayout(gb_ov)

        self.chk_cross = QCheckBox("Crosshair"); self.chk_cross.setChecked(True)
        self.chk_grid = QCheckBox("Grid"); self.chk_grid.setChecked(True)
        self.chk_info = QCheckBox("Info"); self.chk_info.setChecked(True)

        go.addWidget(self.chk_cross, 0, 0)
        go.addWidget(self.chk_grid, 0, 1)
        go.addWidget(self.chk_info, 0, 2)

        l.addWidget(gb_ov)
        l.addStretch(1)

        # ───── Center panel
        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(12)

        self.live_view = LiveViewWidget()
        cv.addWidget(self.live_view, 1)

        self.hist = HistogramWidget()
        cv.addWidget(self.hist, 0)

        splitter.addWidget(self.left)
        splitter.addWidget(center)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)

    def _card(self) -> QFrame:
        w = QFrame()
        w.setObjectName("Card")
        w.setStyleSheet("QFrame#Card{background:#171a20; border:1px solid #23262d; border-radius:12px;}")
        return w
    # ─────────────────────────
    def _wire_ui(self):
        self.btn_start.clicked.connect(self.start_live)
        self.btn_stop.clicked.connect(self.stop_live)
        self.btn_project.clicked.connect(self.project_live_view)

        # captura dedicada
        self.btn_capture_dedicated.clicked.connect(self.on_capture_dedicated)

        # gain sync
        self.sl_gain.valueChanged.connect(self.sp_gain.setValue)
        self.sp_gain.valueChanged.connect(self.sl_gain.setValue)
        self.sp_gain.valueChanged.connect(self.on_gain_changed)

        # exposure
        self.sp_exp.valueChanged.connect(self.on_exposure_changed)

        # ROI
        self.chk_roi.toggled.connect(self.on_roi_toggled)
        self.btn_apply_roi.clicked.connect(self.apply_roi)

        # overlay
        self.chk_cross.toggled.connect(self.on_overlay_changed)
        self.chk_grid.toggled.connect(self.on_overlay_changed)
        self.chk_info.toggled.connect(self.on_overlay_changed)

    # ─────────────────────────
    # Status
    # ─────────────────────────
    def _update_camera_status_label(self):
        if isinstance(self.cam_manager, SimulatedCameraManager):
            self.lbl_cam_status.setText("Cámara: Simulada")
        else:
            ok = getattr(self.cam_manager, "sdk_available", False)
            con = getattr(self.cam_manager, "camera_connected", False)
            if ok and con:
                self.lbl_cam_status.setText("Cámara: ZWO (conectada)")
            elif ok:
                self.lbl_cam_status.setText("Cámara: ZWO (0 detectadas) → simulador")
            else:
                self.lbl_cam_status.setText("Cámara: ZWO (SDK no disponible) → simulador")

    # ─────────────────────────
    # Live controls
    # ─────────────────────────
    def start_live(self):
        ok = self.live.start(12)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        if isinstance(self.cam_manager, SimulatedCameraManager):
            QMessageBox.information(
                self,
                "Cámara no detectada",
                "No se ha detectado una cámara ZWO.\n\n"
                "Se está usando el modo SIMULADO para el Live View."
            )
        return ok

    def stop_live(self):
        self.live.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    # ─────────────────────────
    # Proyector
    # ─────────────────────────
    def project_live_view(self):
        if LiveViewProjector is None:
            QMessageBox.warning(
                self,
                "Proyector no disponible",
                "No se pudo importar LIVE_VIEW_PROJECTOR.PY."
            )
            return

        self._projector = LiveViewProjector()
        self._projector.show()

        def _push(frame):
            try:
                if hasattr(self._projector, "set_frame"):
                    self._projector.set_frame(frame)
            except Exception:
                pass

        try:
            self.live.frame_ready.disconnect(_push)
        except Exception:
            pass
        self.live.frame_ready.connect(_push)

    # ─────────────────────────
    # Camera settings
    # ─────────────────────────
    def on_gain_changed(self, v: int):
        try:
            if hasattr(self.cam_manager, "set_gain"):
                self.cam_manager.set_gain(int(v))
        except Exception:
            pass

    def on_exposure_changed(self, v: float):
        try:
            if hasattr(self.cam_manager, "set_exposure"):
                self.cam_manager.set_exposure(float(v))
        except Exception:
            pass

    # ─────────────────────────
    # ROI
    # ─────────────────────────
    def on_roi_toggled(self, enabled: bool):
        self._roi_enabled = bool(enabled)
        if not self._roi_enabled:
            try:
                if hasattr(self.cam_manager, "set_roi"):
                    self.cam_manager.set_roi(0, 0, 999999, 999999)
            except Exception:
                pass
            self.live_view.set_roi_rect(None)

    def apply_roi(self):
        if not self._roi_enabled:
            return

        x = int(self.sp_rx.value())
        y = int(self.sp_ry.value())
        w = int(self.sp_rw.value())
        h = int(self.sp_rh.value())

        self._roi_rect = QRect(x, y, w, h)
        self.live_view.set_roi_rect(self._roi_rect)

        try:
            if hasattr(self.cam_manager, "set_roi"):
                self.cam_manager.set_roi(x, y, w, h)
        except Exception:
            pass

    # ─────────────────────────
    # Overlay toggles
    # ─────────────────────────
    def on_overlay_changed(self):
        self.live_view.overlay.crosshair = self.chk_cross.isChecked()
        self.live_view.overlay.grid = self.chk_grid.isChecked()
        self.live_view.overlay.info = self.chk_info.isChecked()
        self.live_view.update()

    # ─────────────────────────
    # CAPTURA DEDICADA (MODELO B)
    # ─────────────────────────

    def push_frame(self, frame):
        if self._running:
            self._frames.append(frame.copy())
            if len(self._frames) % 50 == 0:
                print("Frames capturados:", len(self._frames))

    def on_capture_dedicated(self):
        if self._capture_running:
            return

        duration = float(self.sp_cap_exp.value())

        self._video_frames.clear()
        self._capture_running = True
        self._video_capture_end_ts = time.time() + duration

        QMessageBox.information(
            self,
            "Captura iniciada",
            f"Capturando vídeo durante {duration:.2f} s"
        )


    def save_avi(self, frames: list[np.ndarray], path: str, fps: int = 30):
        if not frames:
            raise RuntimeError("No hay frames para guardar")

        h, w = frames[0].shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        writer = cv2.VideoWriter(path, fourcc, fps, (w, h), isColor=True)

        if not writer.isOpened():
            raise RuntimeError("No se pudo abrir el writer AVI")

        for f in frames:
            if f.ndim == 2:
                f = cv2.cvtColor(f, cv2.COLOR_GRAY2BGR)
            writer.write(f)

        writer.release()

    # ─────────────────────────
    # GUARDAR LARGA EXPOSICIÓN EN AVI
    # ─────────────────────────

    def _on_video_captured(self, frames):
        self._capture_running = False

        # desconectar captura
        try:
            self.live.frame_ready.disconnect(self._cap_worker.push_frame)
        except Exception:
            pass

        self._cap_thread.quit()
        self._cap_thread.wait()

        if not frames:
            QMessageBox.warning(self, "Captura", "No se capturaron frames.")
            return

        duration = float(self.sp_cap_exp.value())
        fps_real = max(1, int(round(len(frames) / duration)))

        out_dir = os.path.join(os.getcwd(), "captures")
        os.makedirs(out_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"capture_{ts}.avi")

        # guardar AVI en background
        self._avi_thread = QThread(self)
        self._avi_worker = AviSaveWorker(frames, path, fps_real)

        self._avi_worker.moveToThread(self._avi_thread)
        self._avi_thread.started.connect(self._avi_worker.run)
        self._avi_worker.finished.connect(self._avi_thread.quit)
        self._avi_worker.error.connect(
            lambda e: QMessageBox.critical(self, "Error AVI", e)
        )

        self._avi_thread.start()

        QMessageBox.information(
            self,
            "Captura finalizada",
            f"Vídeo guardándose:\n{path}\n"
            f"Frames: {len(frames)} | FPS: {fps_real}"
        )


    def _save_captured_frame(self, frame: np.ndarray):
        out_dir = os.path.join(os.getcwd(), "captures")
        os.makedirs(out_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"capture_{ts}.png")

        try:
            qimg = _qimage_from_ndarray(frame)
            if qimg.isNull():
                raise RuntimeError("Frame inválido")
            qimg.save(path)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error al guardar",
                f"No se pudo guardar la imagen:\n{e}"
            )
            return

        QMessageBox.information(
            self,
            "Captura guardada",
            f"Imagen guardada en:\n{path}"
        )

    # ─────────────────────────
    # Frame reception
    # ─────────────────────────
    def on_frame(self, frame):
        if frame is None:
            return
        if isinstance(frame, dict) and "frame" in frame:
            frame = frame["frame"]
        if not isinstance(frame, np.ndarray):
            return

        self._last_frame = frame

        # UI
        self.live_view.set_frame(frame)
        self.hist.set_frame(frame)

        # 🔥 CAPTURA DE VÍDEO (FireCapture style)
        if self._capture_running:
            self._video_frames.append(frame.copy())

            if time.time() >= self._video_capture_end_ts:
                self._finish_video_capture()

        # Bus
        if self.bus is not None and hasattr(self.bus, "frame_ready"):
            try:
                self.bus.frame_ready.emit(frame)
            except Exception:
                pass
    
    def _finish_video_capture(self):
        self._capture_running = False

        frames = self._video_frames.copy()
        self._video_frames.clear()

        if not frames:
            QMessageBox.warning(self, "Captura", "No se capturaron frames.")
            return

        duration = float(self.sp_cap_exp.value())
        fps_real = max(1, int(round(len(frames) / duration)))

        out_dir = os.path.join(os.getcwd(), "captures")
        os.makedirs(out_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"capture_{ts}.avi")

        self.save_avi(frames, path, fps=fps_real)

        QMessageBox.information(
            self,
            "Captura finalizada",
            f"Vídeo guardado:\n{path}\n"
            f"Frames: {len(frames)} | FPS: {fps_real}"
        )


