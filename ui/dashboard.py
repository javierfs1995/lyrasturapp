from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDateEdit, QFrame, QSplitter, QStyledItemDelegate
)
from PySide6.QtCore import Qt, QDate, QThread, QTimer, QRect
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWebEngineWidgets import QWebEngineView

from location.location_storage import load_location
from location.map_selector import MapSelector
from workers.forecast_worker import ForecastWorker
from astro.sun import is_night_time


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def score_color(score: int) -> QColor:
    if score >= 80:
        return QColor("#1f6f4a")
    if score >= 60:
        return QColor("#3a7f5f")
    if score >= 40:
        return QColor("#8a7b2e")
    if score >= 20:
        return QColor("#8a4b2e")
    return QColor("#7a2e2e")


def extract_datetime(row: dict):
    if not isinstance(row, dict):
        return None
    if "datetime" in row and isinstance(row["datetime"], datetime):
        return row["datetime"]
    if "time" in row:
        try:
            return datetime.fromisoformat(row["time"])
        except Exception:
            return None
    return None


# ─────────────────────────────────────────────
# DELEGATE PARA ASTROSCORE (CLAVE)
# ─────────────────────────────────────────────
class AstroScoreDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index):
        try:
            score = int(index.data())
        except Exception:
            score = 0

        bg = score_color(score)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(option.rect, bg)

        painter.setPen(Qt.white)
        font = option.font
        font.setBold(True)
        painter.setFont(font)

        painter.drawText(
            option.rect,
            Qt.AlignCenter,
            str(score)
        )
        painter.restore()


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────
class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()

        self.location = load_location()
        self.hourly_data = []

        self.thread = None
        self.worker = None
        self.radar = None

        self._build_ui()

        QTimer.singleShot(0, self.init_radar)
        QTimer.singleShot(0, self.reload_all)

    # ─────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # ─ Header
        header = QHBoxLayout()
        title = QLabel("🌙  Planificación astronómica")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        header.addWidget(title)
        header.addStretch()

        self.btn_loc = QPushButton("📍 Cambiar ubicación")
        self.btn_loc.clicked.connect(self.change_location)

        self.btn_reload = QPushButton("🔄 Actualizar")
        self.btn_reload.clicked.connect(self.reload_all)

        header.addWidget(self.btn_loc)
        header.addWidget(self.btn_reload)
        root.addLayout(header)

        # ─ Info
        info = QHBoxLayout()
        self.lbl_loc = QLabel()
        self.lbl_loc.setStyleSheet("color:#cfd6dd;")
        info.addWidget(self.lbl_loc)
        info.addStretch()

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self.refresh_table)
        info.addWidget(self.date_edit)

        self.lbl_summary = QLabel("—")
        self.lbl_summary.setStyleSheet("color:#cfd6dd;")
        info.addWidget(self.lbl_summary)

        root.addLayout(info)

        # ─ Splitter
        splitter = QSplitter(Qt.Horizontal)

        # ─ Tabla
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Hora", "Nubes", "Humedad", "Viento", "Luna", "AstroScore"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionMode(QTableWidget.NoSelection)

        # 👉 DELEGATE SOLO PARA ASTROSCORE
        self.table.setItemDelegateForColumn(5, AstroScoreDelegate(self.table))

        splitter.addWidget(self.table)

        # ─ Radar
        self.radar_frame = QFrame()
        self.radar_layout = QVBoxLayout(self.radar_frame)
        self.radar_layout.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(self.radar_frame)

        splitter.setStretchFactor(0, 55)
        splitter.setStretchFactor(1, 45)
        splitter.setSizes([700, 500])

        root.addWidget(splitter, 1)

        self.update_location_label()

    # ─────────────────────────
    def update_location_label(self):
        if not self.location:
            self.lbl_loc.setText("Ubicación no definida")
            return

        city = self.location.get("city", "Ubicación personalizada")
        lat = float(self.location["lat"])
        lon = float(self.location["lon"])

        self.lbl_loc.setText(f"{city} | Lat {lat:.4f}, Lon {lon:.4f}")

    # ─────────────────────────
    def change_location(self):
        self.map_selector = MapSelector()
        self.map_selector.location_selected.connect(self.on_location_selected)
        self.map_selector.show()

    def on_location_selected(self):
        self.location = load_location()
        self.update_location_label()
        self.load_radar()
        self.reload_all()

    # ─────────────────────────
    # RADAR
    # ─────────────────────────
    def init_radar(self):
        if self.radar is not None:
            return

        self.radar = QWebEngineView()
        self.radar_layout.addWidget(self.radar)
        self.load_radar()

    def load_radar(self):
        if not self.radar or not self.location:
            return

        lat = self.location["lat"]
        lon = self.location["lon"]

        html = (
            "<html><body style='margin:0'>"
            f"<iframe width='100%' height='100%' "
            f"src='https://embed.windy.com/embed2.html?"
            f"lat={lat}&lon={lon}&zoom=7&overlay=clouds'></iframe>"
            "</body></html>"
        )
        self.radar.setHtml(html)

    # ─────────────────────────
    # FORECAST
    # ─────────────────────────
    def reload_all(self):
        if not self.location or self.thread is not None:
            return

        lat = float(self.location["lat"])
        lon = float(self.location["lon"])

        self.thread = QThread(self)
        self.worker = ForecastWorker(lat, lon)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_forecast_ready)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_forecast_ready(self, data):
        self.hourly_data = data.get("hourly", [])
        self.refresh_table()

    # ─────────────────────────
    def refresh_table(self):
        self.table.setRowCount(0)

        if not self.hourly_data or not self.location:
            return

        lat = float(self.location["lat"])
        lon = float(self.location["lon"])
        selected_date = self.date_edit.date().toPython()

        best = 0
        good_hours = 0

        for row in self.hourly_data:
            dt = extract_datetime(row)
            if not dt or dt.date() != selected_date:
                continue

            if not is_night_time(dt, lat, lon):
                continue

            r = self.table.rowCount()
            self.table.insertRow(r)

            score = int(row.get("astro_score", 0))

            values = [
                dt.strftime("%H:%M"),
                f"{row.get('clouds', 0)}%",
                f"{row.get('humidity', 0)}%",
                f"{row.get('wind', 0)} km/h",
                f"{row.get('moon', 0)}%",
                score,
            ]

            for c, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, item)

            best = max(best, score)
            if score >= 60:
                good_hours += 1

        self.lbl_summary.setText(
            f"Mejor {best}/100 | Ventana ≥60: {good_hours}h"
        )
