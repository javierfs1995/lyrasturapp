# ui/camera_page.py
# CameraPage (NINA-ish shell + FireCapture-ish LiveView)
# - NO depende de fps kw en LiveViewService.start()
# - NO usa FrameBus.instance() (en tu proyecto FrameBus es una función / factory)
# - Si no hay ZWO, usa simulador sin crashear
# - Live View con overlay (crosshair + grid + texto), zoom tipo FireCapture, ROI básico,
#   controles de exposición/ganancia, histograma, y botón para proyectar a otra pantalla (LIVE_VIEW_PROJECTOR.py)

from __future__ import annotations

import time
import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QRect, QSize, QPoint
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QAction,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QSlider,
    QSplitter,
    QSizePolicy,
    QMessageBox,
    QGroupBox,
    QGridLayout,
)

# ─────────────────────────────────────────────
# Optional imports (no romper si faltan)
# ─────────────────────────────────────────────
try:
    from camera.zwo_camera import ZWOCameraManager  # tu fichero: camera/zwo_camera.py
except Exception:
    ZWOCameraManager = None

# Tu proyecto tiene camera/frame_bus.py. A veces FrameBus es una función (factory/singleton).
def _get_frame_bus():
    try:
        from camera.frame_bus import FrameBus  # type: ignore
        # Si FrameBus es función: FrameBus()
        # Si fuera clase: FrameBus() también
        return FrameBus()
    except Exception:
        return None

# Botón para proyectar live view
try:
    from LIVE_VIEW_PROJECTOR import LiveViewProjector  # noqa: N813
except Exception:
    LiveViewProjector = None


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _qimage_from_ndarray(frame: np.ndarray) -> QImage:
    """
    Soporta:
      - Gray HxW uint8/uint16/float
      - RGB/RGBA HxWx3/4 uint8

    FIX: fuerza memoria C-contigua para evitar
    BufferError: underlying buffer is not C-contiguous
    """
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        return QImage()

    # 🔑 FIX CRÍTICO
    arr = np.ascontiguousarray(frame)

    if arr.dtype != np.uint8:
        a = arr.astype(np.float32)
        a -= float(np.min(a)) if a.size else 0.0
        mx = float(np.max(a)) if a.size else 1.0
        if mx <= 0:
            mx = 1.0
        a = (a / mx) * 255.0
        arr = np.clip(a, 0, 255).astype(np.uint8)

    if arr.ndim == 2:
        h, w = arr.shape
        qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
        return qimg.copy()

    if arr.ndim == 3:
        h, w, ch = arr.shape
        if ch == 3:
            qimg = QImage(arr.data, w, h, w * 3, QImage.Format_RGB888)
            return qimg.copy()
        if ch == 4:
            qimg = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888)
            return qimg.copy()

    return QImage()



def _clamp(v: int, a: int, b: int) -> int:
    return max(a, min(b, v))


# ─────────────────────────────────────────────
# Simulated Camera (fallback)
# ─────────────────────────────────────────────
class SimulatedCameraManager:
    """
    Simulador que genera frames tipo "astronomía" (estrellas + ruido + un objeto brillante).
    Implementa lo mínimo que el UI necesita: start_live/stop_live/get_frame/set_gain/set_exposure/set_roi.
    """

    def __init__(self):
        self.sdk_available = False
        self.camera_connected = False
        self._t0 = time.time()

        self._gain = 120
        self._exposure_ms = 20.0
        self._roi = None  # (x,y,w,h)
        self._w = 1280
        self._h = 720

    def start_live(self):
        return True

    def stop_live(self):
        return True

    def set_gain(self, value: int):
        self._gain = int(value)

    def set_exposure(self, ms: float):
        self._exposure_ms = float(ms)

    def set_roi(self, x: int, y: int, w: int, h: int):
        self._roi = (int(x), int(y), int(w), int(h))

    def get_frame(self):
        w, h = self._w, self._h
        img = np.random.normal(10, 6, (h, w)).astype(np.float32)

        # estrellas
        nstars = 250
        xs = np.random.randint(0, w, size=nstars)
        ys = np.random.randint(0, h, size=nstars)
        img[ys, xs] += np.random.uniform(120, 220, size=nstars)

        # "objeto" brillante que deriva un poco
        t = time.time() - self._t0
        cx = w * 0.52 + math.sin(t * 0.35) * 20
        cy = h * 0.48 + math.cos(t * 0.28) * 12

        rr = 9
        x0 = _clamp(int(cx - rr), 0, w - 1)
        x1 = _clamp(int(cx + rr), 0, w - 1)
        y0 = _clamp(int(cy - rr), 0, h - 1)
        y1 = _clamp(int(cy + rr), 0, h - 1)

        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                img[yy, xx] += 250 * math.exp(-d2 / (2 * 2.3**2))

        # "ganancia" y "exposición" influyen (simple)
        gain_scale = 0.6 + (self._gain / 300.0)
        exp_scale = 0.7 + (self._exposure_ms / 80.0)
        img *= (gain_scale * exp_scale)

        img = np.clip(img, 0, 255).astype(np.uint8)

        # ROI recorte
        if self._roi is not None:
            x, y, rw, rh = self._roi
            x = _clamp(x, 0, w - 2)
            y = _clamp(y, 0, h - 2)
            rw = _clamp(rw, 16, w - x)
            rh = _clamp(rh, 16, h - y)
            img = img[y : y + rh, x : x + rw]

        return img


# ─────────────────────────────────────────────
# LiveViewService (QTimer en hilo UI)
# ─────────────────────────────────────────────
class LiveViewService(QObject):
    frame_ready = Signal(object)  # np.ndarray

    def __init__(self, cam_manager, parent=None):
        super().__init__(parent)
        self.cam = cam_manager
        self.timer = QTimer(self)  # IMPORTANTE: creado en hilo UI
        self.timer.timeout.connect(self._tick)
        self._running = False

    def start(self, fps: int = 12):
        # compat con llamadas antiguas:
        #   start(fps=12)  -> OK
        #   start(12)      -> OK
        try:
            fps = int(fps)
        except Exception:
            fps = 12
        fps = max(1, min(60, fps))
        interval = int(1000 / fps)

        if self._running:
            return True

        ok = True
        try:
            if hasattr(self.cam, "start_live"):
                self.cam.start_live()
        except Exception:
            ok = False

        self._running = True
        self.timer.start(interval)
        return ok

    def stop(self):
        if not self._running:
            return True
        self.timer.stop()
        self._running = False
        try:
            if hasattr(self.cam, "stop_live"):
                self.cam.stop_live()
        except Exception:
            pass
        return True

    def is_running(self) -> bool:
        return self._running

    def _tick(self):
        try:
            frame = None
            if hasattr(self.cam, "get_frame"):
                frame = self.cam.get_frame()
            if frame is None:
                return
            self.frame_ready.emit(frame)
        except Exception:
            # evitar crasheos por excepciones en timer
            return


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

        # calcular escala
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

        # overlay
        p.setRenderHint(QPainter.Antialiasing, True)

        if self.overlay.grid:
            pen = QPen(QColor(255, 255, 255, 35), 1)
            p.setPen(pen)
            # 3x3 grid
            for k in (1, 2):
                gx = x + (dw * k) // 3
                gy = y + (dh * k) // 3
                p.drawLine(gx, y, gx, y + dh)
                p.drawLine(x, gy, x + dw, gy)

        if self.overlay.crosshair:
            pen = QPen(QColor(255, 255, 255, 90), 1)
            p.setPen(pen)
            cx = x + dw // 2
            cy = y + dh // 2
            p.drawLine(cx, y, cx, y + dh)
            p.drawLine(x, cy, x + dw, cy)

        if self.overlay.roi and self._roi_rect is not None:
            # ROI en coords de imagen -> convertir a coords de pantalla
            rx = x + int(self._roi_rect.x() * s)
            ry = y + int(self._roi_rect.y() * s)
            rw = int(self._roi_rect.width() * s)
            rh = int(self._roi_rect.height() * s)
            pen = QPen(QColor("#ff9a3d"), 2)
            p.setPen(pen)
            p.drawRect(QRect(rx, ry, rw, rh))

        if self.overlay.info:
            p.setPen(QColor("#cfd6dd"))
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            txt = f"Zoom: {('Fit' if self._fit else f'{self._zoom:.2f}x')}   FPS: {self._fps:.1f}"
            p.drawText(12, 22, txt)


# ─────────────────────────────────────────────
# Histogram Widget
# ─────────────────────────────────────────────
class HistogramWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(120)
        self._hist = None  # np.ndarray shape (256,)
        self._min = 0
        self._max = 255

    def set_frame(self, frame: Optional[np.ndarray]):
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            self._hist = None
            self.update()
            return

        if frame.ndim == 3:
            g = frame[..., 0]
        else:
            g = frame

        if g.dtype != np.uint8:
            a = g.astype(np.float32)
            a -= float(np.min(a))
            mx = float(np.max(a))
            mx = mx if mx > 0 else 1.0
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

        # marco
        p.setPen(QColor("#23262d"))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

        if self._hist is None:
            p.setPen(QColor("#8b95a3"))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(self.rect(), Qt.AlignCenter, "Histograma —")
            return

        w = self.width()
        h = self.height()

        # barras
        pen = QPen(QColor(220, 230, 245, 170), 1)
        p.setPen(pen)

        for i in range(256):
            x = int(i * (w / 256.0))
            v = float(self._hist[i])
            y0 = h - 8
            y1 = int((h - 20) * (1.0 - v))
            p.drawLine(x, y0, x, y1)

        # texto min/max
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
        self._roi_rect = QRect(0, 0, 0, 0)  # coords imagen

        self._last_frame: Optional[np.ndarray] = None

        self._build_ui()
        self._wire_ui()
        self._update_camera_status_label()

    # ─────────────────────────
    def _init_camera_manager(self, cam_manager):
        if cam_manager is not None:
            return cam_manager

        # Intentar ZWO
        if ZWOCameraManager is not None:
            try:
                z = ZWOCameraManager()
                # si SDK disponible pero sin cámara -> simulador
                if getattr(z, "sdk_available", False) and not getattr(z, "camera_connected", False):
                    self.no_camera_detected = True
                    return SimulatedCameraManager()
                # si SDK no disponible -> simulador
                if not getattr(z, "sdk_available", False):
                    self.no_camera_detected = True
                    return SimulatedCameraManager()
                # cámara real conectada
                return z
            except Exception:
                self.no_camera_detected = True
                return SimulatedCameraManager()

        self.no_camera_detected = True
        return SimulatedCameraManager()

    # ─────────────────────────
    # UI
    # ─────────────────────────
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

        # left panel controls
        self.left = self._card()
        self.left.setFixedWidth(340)
        l = QVBoxLayout(self.left)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(12)

        # live controls
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
        self.btn_project.setToolTip("Abre el proyector en otra pantalla (LIVE_VIEW_PROJECTOR.PY)")

        gl.addWidget(self.btn_start, 0, 0, 1, 2)
        gl.addWidget(self.btn_stop, 0, 2, 1, 1)
        gl.addWidget(self.btn_project, 1, 0, 1, 3)

        l.addWidget(gb_live)

        # exposure / gain
        gb_cam = QGroupBox("Cámara")
        gb_cam.setStyleSheet("QGroupBox{font-weight:700;}")
        gc = QGridLayout(gb_cam)
        gc.setContentsMargins(10, 10, 10, 10)
        gc.setHorizontalSpacing(10)
        gc.setVerticalSpacing(8)

        gc.addWidget(QLabel("Exposición (ms)"), 0, 0)
        self.sp_exp = QDoubleSpinBox()
        self.sp_exp.setRange(0.1, 60000.0)
        self.sp_exp.setSingleStep(1.0)
        self.sp_exp.setValue(20.0)
        self.sp_exp.setSuffix(" ms")
        gc.addWidget(self.sp_exp, 0, 1, 1, 2)

        gc.addWidget(QLabel("Ganancia"), 1, 0)
        self.sl_gain = QSlider(Qt.Horizontal)
        self.sl_gain.setRange(0, 300)
        self.sl_gain.setValue(120)
        self.sp_gain = QSpinBox()
        self.sp_gain.setRange(0, 300)
        self.sp_gain.setValue(120)
        gc.addWidget(self.sl_gain, 1, 1)
        gc.addWidget(self.sp_gain, 1, 2)

        l.addWidget(gb_cam)

        # ROI
        gb_roi = QGroupBox("ROI")
        gb_roi.setStyleSheet("QGroupBox{font-weight:700;}")
        gr = QGridLayout(gb_roi)
        gr.setContentsMargins(10, 10, 10, 10)
        gr.setHorizontalSpacing(10)
        gr.setVerticalSpacing(8)

        self.chk_roi = QCheckBox("Activar ROI")
        gr.addWidget(self.chk_roi, 0, 0, 1, 3)

        gr.addWidget(QLabel("X"), 1, 0)
        self.sp_rx = QSpinBox(); self.sp_rx.setRange(0, 99999); self.sp_rx.setValue(0)
        gr.addWidget(self.sp_rx, 1, 1, 1, 2)

        gr.addWidget(QLabel("Y"), 2, 0)
        self.sp_ry = QSpinBox(); self.sp_ry.setRange(0, 99999); self.sp_ry.setValue(0)
        gr.addWidget(self.sp_ry, 2, 1, 1, 2)

        gr.addWidget(QLabel("W"), 3, 0)
        self.sp_rw = QSpinBox(); self.sp_rw.setRange(16, 99999); self.sp_rw.setValue(640)
        gr.addWidget(self.sp_rw, 3, 1, 1, 2)

        gr.addWidget(QLabel("H"), 4, 0)
        self.sp_rh = QSpinBox(); self.sp_rh.setRange(16, 99999); self.sp_rh.setValue(480)
        gr.addWidget(self.sp_rh, 4, 1, 1, 2)

        self.btn_apply_roi = QPushButton("Aplicar ROI")
        gr.addWidget(self.btn_apply_roi, 5, 0, 1, 3)

        l.addWidget(gb_roi)

        # overlay options
        gb_ov = QGroupBox("Overlay")
        gb_ov.setStyleSheet("QGroupBox{font-weight:700;}")
        go = QGridLayout(gb_ov)
        go.setContentsMargins(10, 10, 10, 10)
        go.setHorizontalSpacing(10)
        go.setVerticalSpacing(8)

        self.chk_cross = QCheckBox("Crosshair")
        self.chk_cross.setChecked(True)
        self.chk_grid = QCheckBox("Grid")
        self.chk_grid.setChecked(True)
        self.chk_info = QCheckBox("Info")
        self.chk_info.setChecked(True)
        go.addWidget(self.chk_cross, 0, 0)
        go.addWidget(self.chk_grid, 0, 1)
        go.addWidget(self.chk_info, 0, 2)

        l.addWidget(gb_ov)
        l.addStretch(1)

        # center panel: live view + histogram bottom
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

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 1200])

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

        # gain sync
        self.sl_gain.valueChanged.connect(self.sp_gain.setValue)
        self.sp_gain.valueChanged.connect(self.sl_gain.setValue)
        self.sp_gain.valueChanged.connect(self.on_gain_changed)

        # exposure
        self.sp_exp.valueChanged.connect(self.on_exposure_changed)

        # ROI
        self.chk_roi.toggled.connect(self.on_roi_toggled)
        self.btn_apply_roi.clicked.connect(self.apply_roi)

        # overlay toggles
        self.chk_cross.toggled.connect(self.on_overlay_changed)
        self.chk_grid.toggled.connect(self.on_overlay_changed)
        self.chk_info.toggled.connect(self.on_overlay_changed)

    # ─────────────────────────
    # Status
    # ─────────────────────────
    def _update_camera_status_label(self):
        # mostrar si es real o sim
        if isinstance(self.cam_manager, SimulatedCameraManager):
            self.lbl_cam_status.setText("Cámara: Simulada")
        else:
            # ZWO
            ok = getattr(self.cam_manager, "sdk_available", False)
            con = getattr(self.cam_manager, "camera_connected", False)
            if ok and con:
                self.lbl_cam_status.setText("Cámara: ZWO (conectada)")
            elif ok and not con:
                self.lbl_cam_status.setText("Cámara: ZWO (0 detectadas) → simulador")
            else:
                self.lbl_cam_status.setText("Cámara: ZWO (SDK no disponible) → simulador")

    # ─────────────────────────
    # Live controls
    # ─────────────────────────
    def start_live(self):
        ok = self.live.start(12)  # sin fps= para evitar TypeError si alguien cambia firma
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        # publicar aviso solo cuando entras aquí (no al inicio de app)
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
    def project_live_view(self):
        if LiveViewProjector is None:
            QMessageBox.warning(
                self,
                "Proyector no disponible",
                "No se pudo importar LIVE_VIEW_PROJECTOR.PY.\n"
                "Asegúrate de que existe y expone la clase LiveViewProjector."
            )
            return

        # Abrimos una ventana proyector y le vamos pasando frames
        self._projector = LiveViewProjector()
        self._projector.show()

        # si el proyector tiene método set_frame, lo usamos.
        # si no, evitamos crashear.
        def _push(frame):
            try:
                if hasattr(self._projector, "set_frame"):
                    self._projector.set_frame(frame)
            except Exception:
                pass

        try:
            self.live.frame_ready.disconnect(_push)  # type: ignore
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
            # desactivar ROI en cámara
            try:
                if hasattr(self.cam_manager, "set_roi"):
                    # reset ROI = full frame (para simulador, lo ignorará)
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

        # guardar rect para overlay (coords imagen)
        self._roi_rect = QRect(x, y, w, h)
        self.live_view.set_roi_rect(self._roi_rect)

        # aplicar al manager
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

        # Bus para PolarAlignmentPage
        if self.bus is not None and hasattr(self.bus, "frame_ready"):
            try:
                self.bus.frame_ready.emit(frame)  # type: ignore
            except Exception:
                pass
