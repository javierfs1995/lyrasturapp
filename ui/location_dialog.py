import os
import requests

from PySide6.QtCore import QObject, Slot, QUrl
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings

from astronomy.location import save_location, reverse_geocode, get_elevation


class Bridge(QObject):
    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog

    @Slot(float, float)
    def setCoords(self, lat, lon):
        self.dialog.update_coords(lat, lon)

    @Slot()
    def requestInitial(self):
        self.dialog.send_initial_to_js()


class LocationDialog(QDialog):
    def __init__(self, initial_location=None):
        super().__init__()
        self.setWindowTitle("📍 Seleccionar ubicación de observación")
        self.setMinimumSize(900, 650)

        self.initial_location = initial_location or {}
        self.lat = float(self.initial_location.get("lat", 43.3619))
        self.lon = float(self.initial_location.get("lon", -5.8494))
        self.elevation = int(self.initial_location.get("elevation", 0))

        # Nombre “humano” inicial (si existe)
        self.place_name = self.initial_location.get("name", "") or self.initial_location.get("city", "")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.info = QLabel("Haz click en el mapa para fijar la ubicación exacta.")
        layout.addWidget(self.info)

        # ── WEB VIEW ─────────────────────────────────────────────
        self.view = QWebEngineView()
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)

        html_path = os.path.abspath(os.path.join("resources", "map.html"))
        self.view.setUrl(QUrl.fromLocalFile(html_path))
        layout.addWidget(self.view)

        # ── BOTÓN GUARDAR ───────────────────────────────────────
        self.save_btn = QPushButton("Guardar ubicación")
        self.save_btn.clicked.connect(self.save)
        layout.addWidget(self.save_btn)

        # ── WEBCHANNEL JS ↔ PYTHON ──────────────────────────────
        self.channel = QWebChannel(self.view.page())
        self.bridge = Bridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        self.refresh_label()

    def refresh_label(self):
        name_txt = f" — {self.place_name}" if self.place_name else ""
        self.info.setText(
            f"📍 {self.lat:.6f}°, {self.lon:.6f}°  |  ⛰️ {self.elevation} m{name_txt}"
        )

    def send_initial_to_js(self):
        js = f"window.setInitialPosition({self.lat}, {self.lon}, 12);"
        self.view.page().runJavaScript(js)

    def update_coords(self, lat, lon):
        self.lat = float(lat)
        self.lon = float(lon)

        # Actualizar altitud y nombre en cuanto haces click
        self.elevation = get_elevation(self.lat, self.lon)
        place = reverse_geocode(self.lat, self.lon)
        self.place_name = place.get("name", "")

        self.refresh_label()

    def save(self):
        place = reverse_geocode(self.lat, self.lon)
        self.elevation = get_elevation(self.lat, self.lon)

        save_location({
            "name": place.get("name", "Ubicación"),
            "city": place.get("city", ""),
            "region": place.get("region", ""),
            "country": place.get("country", ""),
            "lat": self.lat,
            "lon": self.lon,
            "elevation": self.elevation
        })
        self.accept()
