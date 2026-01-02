from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt


class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("AstroApp")
        title.setAlignment(Qt.AlignLeft)
        title.setStyleSheet("color:#f2f6f8; font-size:14pt; font-weight:800;")
        layout.addWidget(title)

        self.btn_home = QPushButton("🏠 Dashboard")
        self.btn_location = QPushButton("📍 Ubicación")
        self.btn_polar = QPushButton("🧭 Polar Alignment")
        self.btn_camera = QPushButton("📷 Cámara")
        self.btn_polar2 = QPushButton("🎯 Polar 2 pasos")

        for b in (self.btn_home, self.btn_location, self.btn_polar, self.btn_camera, self.btn_polar2):
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background-color: #1f272c;
                    border: 1px solid #2a353c;
                    border-radius: 10px;
                    padding: 10px 12px;
                    color: #f2f6f8;
                    font-weight: 700;
                    text-align: left;
                }
                QPushButton:hover { background-color: #26323a; }
            """)
            layout.addWidget(b)

        layout.addStretch()
