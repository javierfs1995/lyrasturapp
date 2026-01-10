# ui/live_view_widget.py

import cv2
import numpy as np

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QImage, QPen
from PySide6.QtCore import Qt, QRect


class LiveViewWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.frame: np.ndarray | None = None
        self.zoom_mode = "100"   # "50", "100", "200", "MAX"

        # Overlays
        self.show_crosshair = False
        self.show_grid = False

        # Color / debayer
        self.show_color = False
        self.bayer_pattern = "BGGR"

        self.setStyleSheet("background-color: black;")

        # White balance (preview only)
        self.wb_r = 1.0
        self.wb_g = 1.0
        self.wb_b = 1.0

    # ─────────────────────────────
    # API pública
    # ─────────────────────────────
    def set_frame(self, frame: np.ndarray):
        if frame is None or not isinstance(frame, np.ndarray):
            return

        self.frame = frame
        self.update()

    def set_color(self, enabled: bool):
        self.show_color = bool(enabled)
        self.update()

    def set_bayer_pattern(self, pattern: str):
        self.bayer_pattern = pattern.upper()

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
    # Debayer
    # ─────────────────────────────
    def _debayer(self, frame: np.ndarray) -> np.ndarray:
        bayer_map = {
            "RGGB": cv2.COLOR_BayerRG2RGB,
            "BGGR": cv2.COLOR_BayerBG2RGB,
            "GRBG": cv2.COLOR_BayerGR2RGB,
            "GBRG": cv2.COLOR_BayerGB2RGB,
        }

        code = bayer_map.get(self.bayer_pattern)
        if code is None:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)

        try:
            return cv2.cvtColor(frame, code)
        except Exception:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        
    # ─────────────────────────────
    # Auto-Debayer
    # ─────────────────────────────
    def auto_bayer_from_frame(self, frame: np.ndarray):
        # Heurística simple: prueba dos patrones y mira cuál tiene menos dominante amarilla
        try:
            rgb1 = cv2.cvtColor(frame, cv2.COLOR_BayerRG2RGB)
            rgb2 = cv2.cvtColor(frame, cv2.COLOR_BayerBG2RGB)

            mean1 = rgb1.mean(axis=(0, 1))
            mean2 = rgb2.mean(axis=(0, 1))

            # Si verde domina demasiado → mal patrón
            if abs(mean1[1] - mean1[2]) < abs(mean2[1] - mean2[2]):
                self.bayer_pattern = "RGGB"
            else:
                self.bayer_pattern = "BGGR"
        except Exception:
            pass

    def _auto_detect_bayer(self, frame: np.ndarray):
        """
        Detecta si RGGB o BGGR da colores más coherentes.
        Muy simple pero efectivo (tipo FireCapture).
        """
        try:
            rgb_rggb = cv2.cvtColor(frame, cv2.COLOR_BayerRG2RGB)
            rgb_bggr = cv2.cvtColor(frame, cv2.COLOR_BayerBG2RGB)

            mean_rggb = rgb_rggb.mean(axis=(0, 1))
            mean_bggr = rgb_bggr.mean(axis=(0, 1))

            # Patrón correcto = menos dominante amarilla
            score_rggb = abs(mean_rggb[1] - mean_rggb[2])
            score_bggr = abs(mean_bggr[1] - mean_bggr[2])

            self.bayer_pattern = "RGGB" if score_rggb < score_bggr else "BGGR"

        except Exception:
            # fallback seguro
            self.bayer_pattern = "BGGR"
    
    def set_white_balance(self, r: float, g: float, b: float):
        self.wb_r = max(0.1, r)
        self.wb_g = max(0.1, g)
        self.wb_b = max(0.1, b)
        self.update()


    def _apply_white_balance(self, rgb: np.ndarray) -> np.ndarray:
        wb = np.empty_like(rgb, dtype=np.float32)
        wb[..., 0] = rgb[..., 0] * self.wb_r
        wb[..., 1] = rgb[..., 1] * self.wb_g
        wb[..., 2] = rgb[..., 2] * self.wb_b

        return np.clip(wb, 0, 255).astype(np.uint8)

    # ─────────────────────────────
    # Render FireCapture-like
    # ─────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)

        if self.frame is None:
            painter.end()
            return

        frame = self.frame

        # ── Color / mono
        if frame.ndim == 2:
            if self.show_color:
                rgb = self._debayer(frame)
                rgb = self._apply_white_balance(rgb)
            else:
                rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        else:
            rgb = frame

        # 🔥 CLAVE
        rgb = np.ascontiguousarray(rgb)

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
        # OVERLAYS
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
