from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QStackedWidget, QMessageBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer

from ui.dashboard import DashboardPage
from ui.camera_page import CameraPage

try:
    from ui.polar_alignment_page import PolarAlignmentPage
except Exception:
    PolarAlignmentPage = None


NINA_QSS = """
/* =====================
   Base
===================== */
QMainWindow, QWidget {
    background-color: #14161a;
    color: #cfd6dd;
    font-family: "Segoe UI";
    font-size: 12px;
}
QWidget#Central { background-color: #14161a; }

/* =====================
   Sidebar
===================== */
QFrame#Sidebar {
    background-color: #0f1115;
    border-right: 1px solid #23262d;
}
QLabel#AppTitle {
    color: #e6e6e6;
    font-size: 16px;
    font-weight: 700;
    padding: 14px 12px 2px 12px;
}
QLabel#AppSubtitle {
    color: #8691a0;
    font-size: 11px;
    padding: 0 12px 10px 12px;
}
QPushButton#NavBtn {
    text-align: left;
    padding: 10px 12px;
    border: 1px solid transparent;
    border-radius: 10px;
    color: #cfd6dd;
    background: transparent;
}
QPushButton#NavBtn:hover { background-color: #1b1f27; }
QPushButton#NavBtn[active="true"] {
    background-color: #222a36;
    border-color: #2b3647;
    color: #ffffff;
}

/* =====================
   TopBar
===================== */
QFrame#TopBar {
    background-color: #14161a;
    border-bottom: 1px solid #23262d;
}
QLabel#TopBarTitle {
    color: #e6e6e6;
    font-size: 14px;
    font-weight: 600;
}

/* =====================
   Cards / Panels
===================== */
QFrame#Card {
    background-color: #171a20;
    border: 1px solid #23262d;
    border-radius: 12px;
}
QLabel#CardTitle {
    color: #e6e6e6;
    font-weight: 600;
    font-size: 12px;
}
QLabel#Muted { color: #8b95a3; }

/* =====================
   Inputs
===================== */
QComboBox, QDateEdit, QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #101318;
    border: 1px solid #2a2f39;
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: #2b3647;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #101318;
    border: 1px solid #2a2f39;
    selection-background-color: #2b3647;
    color: #e6e6e6;
}

/* =====================
   Buttons
===================== */
QPushButton {
    background-color: #202633;
    border: 1px solid #2b3647;
    border-radius: 10px;
    padding: 7px 10px;
    color: #e6e6e6;
}
QPushButton:hover { background-color: #273044; }
QPushButton:pressed { background-color: #1b2231; }
QPushButton:disabled { color:#6b7483; background:#171a20; border-color:#23262d; }

/* =====================
   Table
===================== */
QTableWidget {
    background-color: #101318;
    border: 1px solid #23262d;
    border-radius: 12px;
    gridline-color: #23262d;
    selection-background-color: #2b3647;
    selection-color: #ffffff;
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
QTableCornerButton::section { background-color: #14161a; border: none; }

/* =====================
   Splitter
===================== */
QSplitter::handle {
    background-color: #23262d;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AstroApp")
        self.resize(1500, 900)

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

        # Global theme (NINA-ish)
        self.setStyleSheet(NINA_QSS)

        # Pages
        self.pages = QStackedWidget()
        self.pages.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_layout.addWidget(self.pages)

        self.dashboard_page = DashboardPage()
        self.camera_page = CameraPage()

        if PolarAlignmentPage is not None:
            self.polar_page = PolarAlignmentPage()
        else:
            self.polar_page = self._placeholder_page(
                "Polar Alignment",
                "Falta ui/polar_alignment_page.py (PolarAlignmentPage)."
            )

        self.settings_page = self._placeholder_page(
            "Settings",
            "Perfiles (cámara/tubo), rutas, S3, etc."
        )

        self.pages.addWidget(self.dashboard_page)  # 0
        self.pages.addWidget(self.polar_page)      # 1
        self.pages.addWidget(self.camera_page)     # 2
        self.pages.addWidget(self.settings_page)   # 3

        # Start in Dashboard
        self._go(0, "Dashboard")

        # Warn about camera without blocking startup
        if getattr(self.camera_page, "no_camera_detected", False):
            QTimer.singleShot(350, self._show_no_camera_warning)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("AstroApp")
        title.setObjectName("AppTitle")
        subtitle = QLabel("NINA-style shell • Camera FireCapture")
        subtitle.setObjectName("AppSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.btn_dashboard = self._nav_btn("Dashboard", lambda: self._go(0, "Dashboard"))
        self.btn_polar = self._nav_btn("Polar Alignment", lambda: self._go(1, "Polar Alignment"))
        self.btn_camera = self._nav_btn("Camera", lambda: self._go(2, "Camera"))
        self.btn_settings = self._nav_btn("Settings", lambda: self._go(3, "Settings"))

        layout.addWidget(self.btn_dashboard)
        layout.addWidget(self.btn_polar)
        layout.addWidget(self.btn_camera)
        layout.addWidget(self.btn_settings)

        layout.addStretch()
        return sidebar

    def _build_content(self) -> QFrame:
        content = QFrame()
        content.setObjectName("Content")

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

    def _nav_btn(self, text: str, fn) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("NavBtn")
        btn.setProperty("active", False)
        btn.clicked.connect(fn)
        return btn

    def _go(self, idx: int, title: str):
        self.pages.setCurrentIndex(idx)
        self.topbar_title.setText(title)
        self._set_active(idx)

    def _set_active(self, idx: int):
        buttons = [self.btn_dashboard, self.btn_polar, self.btn_camera, self.btn_settings]
        for i, b in enumerate(buttons):
            b.setProperty("active", i == idx)
            b.style().unpolish(b)
            b.style().polish(b)
            b.update()

    def _show_no_camera_warning(self):
        QMessageBox.warning(
            self,
            "Cámara no detectada",
            "No se ha detectado ninguna cámara ZWO.\n\n"
            "Se usará una cámara simulada.\n"
            "La aplicación seguirá funcionando con normalidad."
        )

    def _placeholder_page(self, title: str, msg: str) -> QWidget:
        w = QFrame()
        w.setObjectName("Card")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        t = QLabel(title)
        t.setObjectName("CardTitle")
        d = QLabel(msg)
        d.setObjectName("Muted")
        d.setWordWrap(True)

        lay.addWidget(t)
        lay.addWidget(d)
        lay.addStretch()
        return w
