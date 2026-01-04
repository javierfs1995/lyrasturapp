from __future__ import annotations
import numpy as np

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QSlider, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen

from camera.zwo_camera import ZWOCameraManager
from camera.base_camera import SimulatedCameraManager
from camera.live_view_service import LiveViewService
from camera.frame_bus import FrameBus


# ─────────────────────────────────────────────
# Utils
# ─────────────────────────────────────────────
def np_to_qimage(img: np.ndarray) -> QImage:
    if img.ndim == 2:
        h, w = img.shape
        return QImage(
            img.data, w, h, w, QImage.Format_Grayscale8
        ).copy()

    if img.ndim == 3 and img.shape[2] == 3:
        h, w, _ = img.shape
        return QImage(
            img.data, w, h, w * 3, QImage.Format_RGB888
        ).copy()

    raise ValueError("Formato de imagen no soportado")


# ─────────────────────────────────────────────
# Camera Page
# ─────────────────────────────────────────────
class CameraPage(QWidget):
    def __init__(self):
        super().__init__()

        # ─ Cámara real o simulada
        self.cam_manager = ZWOCameraManager()
        self.no_camera_detected = False

        if not self.cam_manager.camera_connected:
            self.no_camera_detected = True
            self.cam_manager = SimulatedCameraManager(1280, 720)

        self.live = LiveViewService(self.cam_manager)

        # ─ Overlay flags
        self.show_crosshair = True
        self.show_grid = False

        self._build_ui()

        # Recibir frames
        FrameBus().frame_ready.connect(self.on_new_frame)

    # ─────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ────────────────
        # Left panel
        # ────────────────
        left = QFrame()
        left.setFixedWidth(320)
        left_l = QVBoxLayout(left)
        left_l.setSpacing(10)

        self.btn_start = QPushButton("▶ Start Live")
        self.btn_stop = QPushButton("■ Stop Live")
        self.btn_stop.setEnabled(False)

        self.btn_start.clicked.connect(self.start_live)
        self.btn_stop.clicked.connect(self.stop_live)

        left_l.addWidget(self.btn_start)
        left_l.addWidget(self.btn_stop)

        # Gain
        left_l.addWidget(QLabel("Gain"))
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(0, 500)
        self.gain_slider.setValue(100)
        self.gain_slider.valueChanged.connect(self.cam_manager.set_gain)
        left_l.addWidget(self.gain_slider)

        # Exposure
        left_l.addWidget(QLabel("Exposure (ms)"))
        self.exp_slider = QSlider(Qt.Horizontal)
        self.exp_slider.setRange(1, 2000)
        self.exp_slider.setValue(30)
        self.exp_slider.valueChanged.connect(
            lambda v: self.cam_manager.set_exposure(float(v))
        )
        left_l.addWidget(self.exp_slider)

        # Overlay options
        self.chk_cross = QCheckBox("Crosshair")
        self.chk_cross.setChecked(True)
        self.chk_cross.stateChanged.connect(
            lambda v: setattr(self, "show_crosshair", bool(v))
        )

        self.chk_grid = QCheckBox("Grid")
        self.chk_grid.stateChanged.connect(
            lambda v: setattr(self, "show_grid", bool(v))
        )

        left_l.addWidget(self.chk_cross)
        left_l.addWidget(self.chk_grid)

        left_l.addStretch()

        # ────────────────
        # Live view
        # ────────────────
        self.preview = QLabel("Live View")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(900, 700)
        self.preview.setStyleSheet(
            "background:#000; border:1px solid #23262d; border-radius:12px;"
        )

        root.addWidget(left)
        root.addWidget(self.preview, 1)

    # ─────────────────────────────
    def start_live(self):
        self.live.start(fps=12)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_live(self):
        self.live.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    # ─────────────────────────────
    def on_new_frame(self, frame: object):
        if not isinstance(frame, np.ndarray):
            return

        qimg = np_to_qimage(frame)
        pix = QPixmap.fromImage(qimg)

        # Escalar al tamaño del widget
        pix = pix.scaled(
            self.preview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Overlay
        pix = self._draw_overlay(pix)

        self.preview.setPixmap(pix)

    # ─────────────────────────────
    def _draw_overlay(self, pixmap: QPixmap) -> QPixmap:
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        w = pixmap.width()
        h = pixmap.height()

        pen = QPen(Qt.green)
        pen.setWidth(2)
        painter.setPen(pen)

        # ─ Cruz central
        if self.show_crosshair:
            cx, cy = w // 2, h // 2
            painter.drawLine(cx - 30, cy, cx + 30, cy)
            painter.drawLine(cx, cy - 30, cx, cy + 30)

        # ─ Grid (tercios)
        if self.show_grid:
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(w // 3, 0, w // 3, h)
            painter.drawLine(2 * w // 3, 0, 2 * w // 3, h)
            painter.drawLine(0, h // 3, w, h // 3)
            painter.drawLine(0, 2 * h // 3, w, 2 * h // 3)

        painter.end()
        return pixmap
