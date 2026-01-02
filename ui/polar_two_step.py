from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame
)

from camera.manager import CameraManager
from astronomy.polar_two_step_solver import solve_polar_two_step
from astronomy.polar_error_converter import convert_px_to_alt_azi
from equipment.storage import JsonProfileStorage
from ui.overlay_live_view import OverlayLiveView


def np_to_qimage_gray(img: np.ndarray) -> QImage:
    h, w = img.shape
    return QImage(img.data, w, h, w, QImage.Format_Grayscale8).copy()


def thumb_pix(img: QImage):
    return QPixmap.fromImage(img).scaled(
        220, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation
    )


def error_color(arcsec: float) -> str:
    arcmin = arcsec / 60.0
    if arcmin < 1:
        return "#2ecc71"
    if arcmin < 5:
        return "#f1c40f"
    return "#e74c3c"


class PolarTwoStepPage(QWidget):
    def __init__(self, cam_manager: CameraManager):
        super().__init__()
        self.cam = cam_manager.get()

        self.frame1 = None
        self.frame2 = None

        storage = JsonProfileStorage("equipment/profiles.json")
        self.profiles = storage.load_profiles()

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # ── Header ─────────────────────────────
        title = QLabel("🎯 Polar Alignment — 2 pasos")
        title.setStyleSheet("font-size:18pt;font-weight:800;color:#f2f6f8")
        root.addWidget(title)

        top = QHBoxLayout()
        top.addWidget(QLabel("Equipo:"))
        self.profile_cb = QComboBox()
        for k in self.profiles:
            self.profile_cb.addItem(k)
        top.addWidget(self.profile_cb)
        top.addStretch()
        root.addLayout(top)

        # ── Main area (column + live view) ─────
        main = QHBoxLayout()
        main.setSpacing(12)

        # Left column (captures)
        left = QVBoxLayout()
        left.setSpacing(10)

        self.cap1_box = QLabel("Captura 1")
        self.cap2_box = QLabel("Captura 2")

        for b in (self.cap1_box, self.cap2_box):
            b.setFixedSize(240, 160)
            b.setAlignment(Qt.AlignCenter)
            b.setStyleSheet("""
                QLabel {
                    border:1px solid #2a353c;
                    border-radius:8px;
                    background:#0f1418;
                    color:#5f6b73;
                }
            """)

        left.addWidget(self.cap1_box)
        left.addWidget(self.cap2_box)
        left.addStretch()

        # Live View (fixed container)
        self.live = OverlayLiveView(1100, 620)
        self.live.setStyleSheet("background:#000;border-radius:8px")

        main.addLayout(left, 0)
        main.addWidget(self.live, 1)

        root.addLayout(main)

        # ── Results ────────────────────────────
        res = QHBoxLayout()
        self.lbl_azi = QLabel("AZIMUTH ERROR\n—")
        self.lbl_alt = QLabel("ALTITUDE ERROR\n—")
        self.lbl_tot = QLabel("TOTAL ERROR\n—")

        self.lbl_azi.setStyleSheet("color:#1abc9c;font-size:16pt;font-weight:800")
        self.lbl_alt.setStyleSheet("color:#f1c40f;font-size:16pt;font-weight:800")
        self.lbl_tot.setStyleSheet("color:#e74c3c;font-size:16pt;font-weight:900")

        for l in (self.lbl_azi, self.lbl_alt, self.lbl_tot):
            l.setAlignment(Qt.AlignCenter)
            res.addWidget(l, 1)

        root.addLayout(res)

        # ── Controls ───────────────────────────
        controls = QHBoxLayout()

        self.b1 = QPushButton("📌 Captura 1")
        self.b2 = QPushButton("📌 Captura 2")
        self.bc = QPushButton("🧮 Calcular")
        self.br = QPushButton("↺ Reiniciar")

        self.b2.setEnabled(False)
        self.bc.setEnabled(False)

        self.b1.clicked.connect(self.capture1)
        self.b2.clicked.connect(self.capture2)
        self.bc.clicked.connect(self.calculate)
        self.br.clicked.connect(self.reset)

        for b in (self.b1, self.b2, self.bc, self.br):
            b.setStyleSheet("""
                QPushButton {
                    background:#1f272c;
                    border:1px solid #2a353c;
                    border-radius:8px;
                    padding:8px 18px;
                    font-weight:700;
                }
                QPushButton:disabled {
                    background:#161c20;
                    color:#5f6b73;
                }
            """)
            controls.addWidget(b)

        controls.addStretch()
        root.addLayout(controls)

        # ── Timer ─────────────────────────────
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(200)

    # ─────────────────────────────────────────
    def refresh(self):
        if self.cam.is_connected():
            self.live.set_image(np_to_qimage_gray(self.cam.get_frame()))

    def capture1(self):
        self.frame1 = self.cam.get_frame().copy()
        self.cap1_box.setPixmap(thumb_pix(np_to_qimage_gray(self.frame1)))
        self.b2.setEnabled(True)

    def capture2(self):
        self.frame2 = self.cam.get_frame().copy()
        self.cap2_box.setPixmap(thumb_pix(np_to_qimage_gray(self.frame2)))
        self.bc.setEnabled(True)

    def calculate(self):
        if self.frame1 is None or self.frame2 is None:
            return

        res = solve_polar_two_step(self.frame1, self.frame2)
        if not res.ok:
            return

        self.live.set_rotation_center(res.center_xy)

        prof = self.profiles[self.profile_cb.currentText()]
        ang = convert_px_to_alt_azi(
            dx_px=res.offset_xy[0],
            dy_px=res.offset_xy[1],
            pixel_um=prof.camera.pixel_um,
            focal_mm=prof.effective_focal,
            north_orientation="N_ARRIBA"
        )

        c = error_color(ang.total_arcsec)

        self.lbl_azi.setText(f"AZIMUTH ERROR\n{ang.azi_text}\n{ang.azi_move}")
        self.lbl_alt.setText(f"ALTITUDE ERROR\n{ang.alt_text}\n{ang.alt_move}")
        self.lbl_tot.setText(f"TOTAL ERROR\n{ang.total_text}")
        self.lbl_tot.setStyleSheet(f"color:{c};font-size:18pt;font-weight:900")

    def reset(self):
        self.frame1 = None
        self.frame2 = None
        self.cap1_box.clear()
        self.cap2_box.clear()
        self.live.clear_overlay()
        self.b2.setEnabled(False)
        self.bc.setEnabled(False)
