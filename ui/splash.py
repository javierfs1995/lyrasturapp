from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt, QTimer


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()

        self.setFixedSize(420, 220)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setStyleSheet("""
            QWidget {
                background-color: #0f1418;
                border: 1px solid #2a353c;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(16)

        self.title = QLabel("AstroApp")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet(
            "font-size:22pt;font-weight:800;color:#e6eef2"
        )

        self.subtitle = QLabel("Astrofotografía & Planificación")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setStyleSheet(
            "font-size:10pt;color:#9aa4ab"
        )

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminado
        self.progress.setFixedHeight(10)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background:#1b2328;
                border-radius:5px;
            }
            QProgressBar::chunk {
                background:#4fa3ff;
                border-radius:5px;
            }
        """)

        self.status = QLabel("Iniciando…")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet(
            "font-size:9pt;color:#b8c3ca"
        )

        layout.addStretch()
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addStretch()
        layout.addWidget(self.progress)
        layout.addWidget(self.status)

    def set_status(self, text: str):
        self.status.setText(text)
