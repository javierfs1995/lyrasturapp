from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QImage
from PySide6.QtCore import Qt
import cv2


class LiveViewProjector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live View Projector")
        self.frame = None
        self.resize(800, 600)

    def update_frame(self, frame):
        self.frame = frame
        self.update()

    def paintEvent(self, event):
        if self.frame is None:
            return

        rgb = cv2.cvtColor(self.frame, cv2.COLOR_GRAY2RGB)
        h, w, _ = rgb.shape

        img = QImage(
            rgb.data,
            w,
            h,
            3 * w,
            QImage.Format_RGB888
        )

        painter = QPainter(self)
        painter.drawImage(self.rect(), img)
        painter.end()
