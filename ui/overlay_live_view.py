from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QImage, QFont
from PySide6.QtCore import Qt, QRectF, QPointF


class OverlayLiveView(QWidget):
    """
    Live View con overlays:
    - imagen escalada al tamaño del widget
    - cruz central
    - cruz centro de rotación
    - flecha ALT / AZI
    """
    def __init__(self, width: int, height: int):
        super().__init__()
        self.setFixedSize(width, height)

        self.image: QImage | None = None

        self.rot_center: tuple[float, float] | None = None
        self.show_center = True

    # ─────────────────────────────────────────────
    def set_image(self, img: QImage):
        self.image = img
        self.update()

    def set_rotation_center(self, center_xy: tuple[float, float] | None):
        self.rot_center = center_xy
        self.update()

    def clear_overlay(self):
        self.rot_center = None
        self.update()

    # ─────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2

        # ── Fondo ─────────────────────────────────
        p.fillRect(self.rect(), Qt.black)

        # ── Imagen ESCALADA ───────────────────────
        if self.image:
            img_w = self.image.width()
            img_h = self.image.height()

            scale = min(w / img_w, h / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale

            x0 = (w - draw_w) / 2
            y0 = (h - draw_h) / 2

            target = QRectF(x0, y0, draw_w, draw_h)
            source = QRectF(0, 0, img_w, img_h)

            p.drawImage(target, self.image, source)

            # Guardamos transformación para overlays
            self._scale = scale
            self._offset = QPointF(x0, y0)
        else:
            self._scale = 1.0
            self._offset = QPointF(0, 0)

        # ── Cruz central (del campo) ─────────────
        if self.show_center:
            pen = QPen(Qt.green)
            pen.setWidth(1)
            p.setPen(pen)
            p.drawLine(cx - 15, cy, cx + 15, cy)
            p.drawLine(cx, cy - 15, cx, cy + 15)

        # ── Error polar ──────────────────────────
        if self.rot_center:
            rx, ry = self.rot_center

            # Convertir coords imagen → widget
            rx_w = self._offset.x() + rx * self._scale
            ry_w = self._offset.y() + ry * self._scale

            # Cruz centro rotación
            pen_rot = QPen(Qt.red)
            pen_rot.setWidth(2)
            p.setPen(pen_rot)
            p.drawLine(rx_w - 12, ry_w, rx_w + 12, ry_w)
            p.drawLine(rx_w, ry_w - 12, rx_w, ry_w + 12)

            # Flecha centro → error
            pen_arrow = QPen(Qt.yellow)
            pen_arrow.setWidth(2)
            p.setPen(pen_arrow)
            p.drawLine(cx, cy, rx_w, ry_w)

            # Texto ALT / AZI
            dx = rx_w - cx
            dy = ry_w - cy

            az_txt = "AZI →" if dx > 0 else "AZI ←"
            alt_txt = "ALT ↓" if dy > 0 else "ALT ↑"

            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
            p.setFont(font)

            p.drawText(
                QPointF(cx + dx / 2 + 6, cy + dy / 2 - 6),
                f"{az_txt}  {alt_txt}"
            )

        p.end()
