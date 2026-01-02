from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtCore import Qt, QPointF


class PolarView(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 400)

        self.sensor_center = None
        self.polar_center = None

    def set_centers(self, sensor_center, polar_center):
        self.sensor_center = sensor_center
        self.polar_center = polar_center
        self.update()

    def paintEvent(self, event):
        if not self.sensor_center or not self.polar_center:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Escalado simple (imagen → widget)
        w, h = self.width(), self.height()
        sx, sy = w / 640, h / 480  # por ahora fijo (luego dinámico)

        def map_point(p):
            return QPointF(p[0] * sx, p[1] * sy)

        sc = map_point(self.sensor_center)
        pc = map_point(self.polar_center)

        # Centro del sensor (azul)
        painter.setPen(QPen(QColor("#4fa3ff"), 2))
        painter.drawEllipse(sc, 6, 6)

        # Centro polar (verde)
        painter.setPen(QPen(QColor("#4dff88"), 2))
        painter.drawEllipse(pc, 8, 8)

        # Línea entre ambos
        painter.setPen(QPen(QColor("#ffcc66"), 1, Qt.DashLine))
        painter.drawLine(sc, pc)

        painter.end()
