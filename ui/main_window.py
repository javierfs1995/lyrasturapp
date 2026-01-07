from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QStackedWidget, QMessageBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer

from ui.dashboard import DashboardPage
from ui.camera_page import CameraPage
from ui.sequence_page import SequencePage

try:
    from ui.polar_alignment_page import PolarAlignmentPage
except Exception:
    PolarAlignmentPage = None


# ─────────────────────────────────────────────
# NINA-style global theme
# ─────────────────────────────────────────────
NINA_QSS = """
QMainWindow, QWidget {
    background-color: #14161a;
    color: #cfd6dd;
    font-family: "Segoe UI";
    font-size: 12px;
}

QWidget#Central {
    background-color: #14161a;
}

/* ───────── Sidebar ───────── */
QFrame#Sidebar {
    background-color: #0b0d10;
    border-right: 1px solid #23262d;
}

QPushButton#IconBtn {
    background: transparent;
    border: none;
    border-radius: 12px;
    font-size: 22px;
    color: #8b95a3;
}

QPushButton#IconBtn:hover {
    background-color: #1b1f27;
    color: #ffffff;
}

QPushButton#IconBtn:checked {
    background-color: #222a36;
    color: #ffffff;
}

/* ───────── TopBar ───────── */
QFrame#TopBar {
    background-color: #14161a;
    border-bottom: 1px solid #23262d;
}

QLabel#TopBarTitle {
    color: #e6e6e6;
    font-size: 14px;
    font-weight: 600;
}

/* ───────── Cards ───────── */
QFrame#Card {
    background-color: #171a20;
    border: 1px solid #23262d;
    border-radius: 12px;
}

QLabel#CardTitle {
    color: #e6e6e6;
    font-weight: 600;
}

QLabel#Muted {
    color: #8b95a3;
}

/* ───────── Tables ───────── */
QTableWidget {
    background-color: #101318;
    border: 1px solid #23262d;
    border-radius: 12px;
    gridline-color: #23262d;
}

QHeaderView::section {
    background-color: #14161a;
    color: #e6e6e6;
    border: none;
    border-bottom: 1px solid #23262d;
    padding: 8px 6px;
    font-weight: 600;
}

QTableWidget::item {
    border-bottom: 1px solid #1f2430;
    padding-left: 6px;
    padding-right: 6px;
}

/* ───────── Splitter ───────── */
QSplitter::handle {
    background-color: #23262d;
}
"""


# ─────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AstroApp")
        self.resize(1500, 900)

        # ─ Central layout
        central = QWidget()
        central.setObjectName("Central")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = self._build_sidebar()
        self.content = self._build_content()

        root.addWidget(self.sidebar)
        root.addWidget(self.content)
        self.setCentralWidget(central)

        self.setStyleSheet(NINA_QSS)

        # ─ Pages
        self.pages = QStackedWidget()
        self.pages.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_layout.addWidget(self.pages)

        self.dashboard_page = DashboardPage()
        self.camera_page = CameraPage()
        self.sequence_page = SequencePage(
            self.camera_page.cam_manager,
            self.camera_page.live
        )

        if PolarAlignmentPage:
            self.polar_page = PolarAlignmentPage()
        else:
            self.polar_page = self._placeholder_page(
                "Polar Alignment",
                "polar_alignment_page.py no disponible"
            )

        self.settings_page = self._placeholder_page(
            "Settings",
            "Configuración general"
        )

        self.pages.addWidget(self.dashboard_page)  # 0
        self.pages.addWidget(self.polar_page)      # 1
        self.pages.addWidget(self.camera_page)     # 2
        self.pages.addWidget(self.sequence_page)   # 3
        self.pages.addWidget(self.settings_page)   # 3

        self._go(0, "Dashboard")

    # ───────────────────────── Sidebar
    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(72)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        def icon_btn(icon, tooltip, fn):
            btn = QPushButton(icon)
            btn.setObjectName("IconBtn")
            btn.setToolTip(tooltip)
            btn.setCheckable(True)
            btn.setFixedSize(48, 48)
            btn.clicked.connect(fn)
            return btn

        self.btn_dashboard = icon_btn("🏠", "Dashboard", lambda: self._go(0, "Dashboard"))
        self.btn_polar     = icon_btn("🧭", "Polar Alignment", lambda: self._go(1, "Polar Alignment"))
        self.btn_camera    = icon_btn("📷", "Camera", lambda: self._go(2, "Camera"))
        self.btn_sequence    = icon_btn("🎞️​", "Secuencias", lambda: self._go(3, "Secuencias"))
        self.btn_settings  = icon_btn("⚙", "Settings", lambda: self._go(4, "Settings"))

        layout.addWidget(self.btn_dashboard, alignment=Qt.AlignCenter)
        layout.addWidget(self.btn_polar, alignment=Qt.AlignCenter)
        layout.addWidget(self.btn_camera, alignment=Qt.AlignCenter)
        layout.addWidget(self.btn_sequence, alignment=Qt.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.btn_settings, alignment=Qt.AlignCenter)

        return sidebar

    # ───────────────────────── Content
    def _build_content(self) -> QFrame:
        content = QFrame()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(12, 8, 12, 8)

        self.topbar_title = QLabel("Dashboard")
        self.topbar_title.setObjectName("TopBarTitle")

        topbar_layout.addWidget(self.topbar_title)
        topbar_layout.addStretch()

        outer.addWidget(topbar)

        container = QWidget()
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(12)

        outer.addWidget(container)
        return content

    # ───────────────────────── Navigation
    def _go(self, idx: int, title: str):
        self.pages.setCurrentIndex(idx)
        self.topbar_title.setText(title)
        self._set_active(idx)

    def _set_active(self, idx: int):
        buttons = [
            self.btn_dashboard,
            self.btn_polar,
            self.btn_camera,
            self.btn_settings
        ]
        for i, btn in enumerate(buttons):
            btn.setChecked(i == idx)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    # ───────────────────────── Placeholder
    def _placeholder_page(self, title: str, msg: str) -> QWidget:
        w = QFrame()
        w.setObjectName("Card")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)

        t = QLabel(title)
        t.setObjectName("CardTitle")
        d = QLabel(msg)
        d.setObjectName("Muted")
        d.setWordWrap(True)

        lay.addWidget(t)
        lay.addWidget(d)
        lay.addStretch()
        return w
