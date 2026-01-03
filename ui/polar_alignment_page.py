import numpy as np
import cv2

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QImage

from astro.star_detection import detect_polaris
from astro.polar_math import polar_error_from_pixels


# ─────────────────────────────────────────────
# Live View + Overlay
# ─────────────────────────────────────────────
class PolarLiveView(QWidget):
    def __init__(self):
        super().__init__()
        self._frame: QImage | None = None

        self.error_arcmin = 0.0
        self.alt_arcmin = 0.0
        self.az_arcmin = 0.0

    def set_frame(self, img: QImage | None):
        self._frame = img
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0b0d10"))

        # ───── dibujar frame ─────
        if self._frame and not self._frame.isNull():
            scaled = self._frame.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawImage(x, y, scaled)

            cx = x + scaled.width() // 2
            cy = y + scaled.height() // 2
        else:
            cx = self.width() // 2
            cy = self.height() // 2

        # ───── cruz central ─────
        p.setPen(QPen(QColor("#cfd6dd"), 1))
        p.drawLine(cx - 25, cy, cx + 25, cy)
        p.drawLine(cx, cy - 25, cx, cy + 25)

        # ───── círculo de referencia ─────
        p.setPen(QPen(QColor("#4fa3ff"), 2))
        p.drawEllipse(cx - 90, cy - 90, 180, 180)

        # ───── texto informativo ─────
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.setPen(QColor("#ffffff"))
        p.drawText(14, 28, f"Error: {self.error_arcmin:.2f}′")
        p.drawText(14, 50, f"ALT {self.alt_arcmin:+.2f}′")
        p.drawText(14, 72, f"AZ  {self.az_arcmin:+.2f}′")

        p.end()


# ─────────────────────────────────────────────
# Página principal
# ─────────────────────────────────────────────
class PolarAlignmentPage(QWidget):
    def __init__(self):
        super().__init__()

        # Perfil óptico (temporal, luego configurable)
        self.focal_mm = 700.0
        self.pixel_size_um = 2.0  # ASI678MC

        self._last_gray = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ─ Live view
        self.view = PolarLiveView()
        root.addWidget(self.view, 1)

        # ─ Panel lateral
        side = QFrame()
        side.setFixedWidth(320)
        side.setStyleSheet("background:#171a20; border-left:1px solid #23262d;")
        side_l = QVBoxLayout(side)
        side_l.setContentsMargins(12, 12, 12, 12)
        side_l.setSpacing(10)

        title = QLabel("Polar Alignment")
        title.setStyleSheet("font-size:14px; font-weight:700;")
        side_l.addWidget(title)

        self.lbl_status = QLabel("Ajuste semi-en-vivo (Polaris)")
        self.lbl_status.setStyleSheet("color:#8b95a3;")
        side_l.addWidget(self.lbl_status)

        self.btn_start = QPushButton("▶ Iniciar ajuste")
        self.btn_stop = QPushButton("⏹ Detener")
        self.btn_stop.setEnabled(False)

        side_l.addWidget(self.btn_start)
        side_l.addWidget(self.btn_stop)
        side_l.addStretch()

        root.addWidget(side)

        # ─ Timer para control lógico (no captura)
        self.timer = QTimer(self)
        self.timer.setInterval(800)
        self.timer.timeout.connect(self._process_alignment)

        self.btn_start.clicked.connect(self._start)
        self.btn_stop.clicked.connect(self._stop)

    # ─────────────────────────
    # API pública: recibe frames desde ZWO
    # ─────────────────────────
    def set_frame(self, img: QImage):
        self.view.set_frame(img)

        # Convertir a numpy grayscale
        gray = img.convertToFormat(QImage.Format_Grayscale8)
        w, h = gray.width(), gray.height()
        ptr = gray.bits()
        ptr.setsize(w * h)
        self._last_gray = np.frombuffer(ptr, np.uint8).reshape((h, w))

    # ─────────────────────────
    def _start(self):
        self.timer.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("Ajuste activo… mueve la montura")

    def _stop(self):
        self.timer.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("Ajuste detenido")

    # ─────────────────────────
    def _process_alignment(self):
        if self._last_gray is None:
            return

        polaris = detect_polaris(self._last_gray)
        if polaris is None:
            return

        h, w = self._last_gray.shape
        cx, cy = w / 2, h / 2

        dx = polaris[0] - cx
        dy = polaris[1] - cy

        res = polar_error_from_pixels(
            dx_px=dx,
            dy_px=dy,
            pixel_size_um=self.pixel_size_um,
            focal_mm=self.focal_mm
        )

        self.view.error_arcmin = res["error_arcmin"]
        self.view.alt_arcmin = res["alt_arcmin"]
        self.view.az_arcmin = res["az_arcmin"]
        self.view.update()
