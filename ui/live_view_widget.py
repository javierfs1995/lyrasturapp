import cv2
import numpy as np

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QImage, QPen
from PySide6.QtCore import Qt, QRect


class LiveViewWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.frame = None
        self.zoom_mode = "100"   # "50", "100", "200", "MAX"

        # Overlays
        self.show_crosshair = False
        self.show_grid = False

        self.setStyleSheet("background-color: black;")

    # ─────────────────────────────
    # API pública
    # ─────────────────────────────
    def update_frame(self, frame: np.ndarray):
        self.frame = frame
        self.update()

    def set_zoom(self, mode: str):
        self.zoom_mode = mode
        self.update()

    def toggle_crosshair(self):
        self.show_crosshair = not self.show_crosshair
        self.update()

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.update()

    def clear_overlays(self):
        self.show_crosshair = False
        self.show_grid = False
        self.update()

    # ─────────────────────────────
    # Render FireCapture-like
    # ─────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)

        if self.frame is None:
            painter.end()
            return

        # Imagen
        rgb = cv2.cvtColor(self.frame, cv2.COLOR_GRAY2RGB)
        h, w, _ = rgb.shape

        image = QImage(
            rgb.data,
            w,
            h,
            3 * w,
            QImage.Format_RGB888
        )

        canvas_w = self.width()
        canvas_h = self.height()

        # ── Zoom FireCapture
        if self.zoom_mode == "50":
            scale = 0.5
        elif self.zoom_mode == "100":
            scale = 1.0
        elif self.zoom_mode == "200":
            scale = 2.0
        elif self.zoom_mode == "MAX":
            scale = min(canvas_w / w, canvas_h / h)
        else:
            scale = 1.0

        draw_w = int(w * scale)
        draw_h = int(h * scale)

        # Posición
        x = 0
        y = 0
        if self.zoom_mode == "MAX":
            x = (canvas_w - draw_w) // 2
            y = (canvas_h - draw_h) // 2

        target = QRect(x, y, draw_w, draw_h)
        painter.drawImage(target, image)

        # ─────────────────────────────
        # OVERLAYS (FireCapture)
        # ─────────────────────────────
        pen = QPen(Qt.green)
        pen.setWidth(1)
        painter.setPen(pen)

        # Crosshair
        if self.show_crosshair:
            cx = target.x() + target.width() // 2
            cy = target.y() + target.height() // 2
            painter.drawLine(cx, target.y(), cx, target.y() + target.height())
            painter.drawLine(target.x(), cy, target.x() + target.width(), cy)

        # Grid (3x3)
        if self.show_grid:
            for i in range(1, 3):
                gx = target.x() + i * target.width() // 3
                gy = target.y() + i * target.height() // 3
                painter.drawLine(gx, target.y(), gx, target.y() + target.height())
                painter.drawLine(target.x(), gy, target.x() + target.width(), gy)

        painter.end()
