from PySide6.QtWidgets import QWidget, QVBoxLayout
from ui.camera_page import LiveViewWidget, HistogramWidget

class LiveViewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.live_view = LiveViewWidget()
        self.histogram = HistogramWidget()

        layout.addWidget(self.live_view, 1)
        layout.addWidget(self.histogram, 0)
