from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QGroupBox, QSlider, QCheckBox, QComboBox, QFrame
)
from PySide6.QtCore import Qt, QTimer

from ui.live_view_widget import LiveViewWidget
from camera.zwo_camera import ZWOCameraManager
from camera.simulated_camera import SimulatedCameraManager


class CameraPage(QWidget):
    def __init__(self, cam_manager=None):
        super().__init__()

        # ─────────────────────────────────────────────
        # Inicialización de cámara (SIN popups)
        # ─────────────────────────────────────────────
        self.no_camera_detected = False

        self.cam_manager = cam_manager or ZWOCameraManager()

        if (
            not getattr(self.cam_manager, "sdk_available", False)
            or not getattr(self.cam_manager, "camera_connected", False)
        ):
            print("[CameraPage] No se detectó cámara ZWO, usando simulador")
            self.no_camera_detected = True
            self.cam_manager = SimulatedCameraManager()

        # ─────────────────────────────────────────────
        # Estilo FireCapture
        # ─────────────────────────────────────────────
        self.setObjectName("CameraPage")
        self.setStyleSheet("""
            QWidget#CameraPage {
                background-color: #2b2b2b;
                color: #dddddd;
            }
            QGroupBox {
                border: 1px solid #444;
                margin-top: 6px;
                font-size: 11px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
            }
            QLabel {
                font-size: 11px;
            }
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #555;
            }
            QSlider::handle:horizontal {
                background: #aaa;
                width: 10px;
                margin: -6px 0;
            }
        """)

        self._build_ui()
        self._setup_timer()

    # ─────────────────────────────────────────────
    # UI STRUCTURE
    # ─────────────────────────────────────────────
    def _build_ui(self):
        root_h = QHBoxLayout()
        root_h.setContentsMargins(8, 8, 8, 8)
        root_h.setSpacing(8)

        root_h.addWidget(self._build_left_panel())

        self.live_view = LiveViewWidget()
        self.live_view.setFixedSize(1024, 768)
        root_h.addWidget(self.live_view, alignment=Qt.AlignCenter)

        root_h.addWidget(self._build_right_panel())

        root_v = QVBoxLayout(self)
        root_v.addLayout(root_h)
        root_v.addWidget(self._build_status_bar())

    # ─────────────────────────────────────────────
    # LEFT PANEL
    # ─────────────────────────────────────────────
    def _build_left_panel(self):
        panel = QVBoxLayout()
        panel.setSpacing(6)

        panel.addWidget(self._image_group())
        panel.addWidget(self._control_group())
        panel.addWidget(self._capture_group())
        panel.addWidget(self._status_group())
        panel.addStretch()

        container = QWidget()
        container.setLayout(panel)
        container.setFixedWidth(260)
        return container

    def _image_group(self):
        box = QGroupBox("Image")
        layout = QVBoxLayout()

        layout.addWidget(QCheckBox("16 Bit"))
        layout.addWidget(QCheckBox("Bin 2x"))
        layout.addWidget(QLabel("Resolution: MAX (1936 x 1096)"))

        layout.addWidget(QLabel("ROI"))
        layout.addWidget(QLabel("X [0]   Y [0]"))
        layout.addWidget(QLabel("W [640] H [480]"))

        box.setLayout(layout)
        return box

    def _control_group(self):
        box = QGroupBox("Control")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Gain"))
        self.gain_slider = self._slider()
        self.gain_slider.valueChanged.connect(self.cam_manager.set_gain)
        layout.addWidget(self.gain_slider)

        layout.addWidget(QLabel("Exposure (ms)"))
        self.exp_slider = self._slider()
        self.exp_slider.valueChanged.connect(
            lambda v: self.cam_manager.set_exposure(v)
        )
        layout.addWidget(self.exp_slider)

        layout.addWidget(QLabel("Gamma"))
        layout.addWidget(self._slider())

        layout.addWidget(QCheckBox("AutoHist"))

        box.setLayout(layout)
        return box

    def _capture_group(self):
        box = QGroupBox("Capture")
        layout = QVBoxLayout()

        self.btn_start = QPushButton("▶ START")
        self.btn_stop = QPushButton("■ STOP")
        self.btn_stop.setEnabled(False)

        self.btn_start.clicked.connect(self.start_live)
        self.btn_stop.clicked.connect(self.stop_live)

        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_stop)

        box.setLayout(layout)
        return box

    def _status_group(self):
        box = QGroupBox("Status")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("FPS: --"))
        layout.addWidget(QLabel("RAM: --"))
        layout.addWidget(QLabel("Disk: OK"))

        box.setLayout(layout)
        return box

    # ─────────────────────────────────────────────
    # RIGHT PANEL
    # ─────────────────────────────────────────────
    def _build_right_panel(self):
        panel = QVBoxLayout()
        panel.setSpacing(6)

        box = QGroupBox("Options")
        layout = QVBoxLayout()

        for txt in ["50%", "100%", "200%", "MAX"]:
            btn = QPushButton(txt)
            btn.clicked.connect(lambda _, t=txt: self.live_view.set_zoom(t.replace("%", "")))
            layout.addWidget(btn)

        layout.addSpacing(10)

        btn_cross = QPushButton("Crosshair")
        btn_grid = QPushButton("Grid")
        btn_clear = QPushButton("Clear Overlay")

        btn_cross.clicked.connect(self.live_view.toggle_crosshair)
        btn_grid.clicked.connect(self.live_view.toggle_grid)
        btn_clear.clicked.connect(self.live_view.clear_overlays)

        layout.addWidget(btn_cross)
        layout.addWidget(btn_grid)
        layout.addWidget(btn_clear)

        box.setLayout(layout)
        panel.addWidget(box)
        panel.addStretch()

        container = QWidget()
        container.setLayout(panel)
        container.setFixedWidth(180)
        return container

    # ─────────────────────────────────────────────
    # STATUS BAR
    # ─────────────────────────────────────────────
    def _build_status_bar(self):
        bar = QFrame()
        bar.setFixedHeight(28)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.addWidget(QLabel("Camera: ZWO / Simulated"))
        layout.addStretch()
        return bar

    # ─────────────────────────────────────────────
    # LIVE LOOP
    # ─────────────────────────────────────────────
    def _setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

    def start_live(self):
        self.cam_manager.start_live()
        self.timer.start(500)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_live(self):
        self.timer.stop()
        self.cam_manager.stop_live()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def update_frame(self):
        frame = self.cam_manager.get_frame()
        if frame is not None:
            self.live_view.update_frame(frame)

    def _slider(self):
        s = QSlider(Qt.Horizontal)
        s.setRange(0, 100)
        return s
