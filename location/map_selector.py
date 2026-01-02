from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QMessageBox
from PySide6.QtWebEngineWidgets import QWebEngineView

from location.location_storage import save_location


HTML_MAP = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Map Selector</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<style>
  html, body, #map { height:100%; margin:0; }
</style>
</head>
<body>
<div id="map"></div>
<script>
var map = L.map('map').setView([43.36, -5.85], 7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

window.selectedLat = null;
window.selectedLon = null;
var marker = null;

map.on('click', function(e) {
  if (marker) map.removeLayer(marker);
  marker = L.marker(e.latlng).addTo(map);
  window.selectedLat = e.latlng.lat;
  window.selectedLon = e.latlng.lng;
});
</script>
</body>
</html>
"""


class MapSelector(QWidget):
    location_selected = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Seleccionar ubicación")
        self.resize(800, 600)

        self._lat = None
        self._lon = None

        layout = QVBoxLayout(self)

        self.web = QWebEngineView()
        self.web.setHtml(HTML_MAP)
        layout.addWidget(self.web)

        btn = QPushButton("💾 Guardar ubicación")
        btn.clicked.connect(self.save)
        layout.addWidget(btn)

    # ─────────────────────────────────────────────
    def save(self):
        """
        Obtiene lat/lon desde JS y guarda la ubicación.
        """
        # 1️⃣ Pedir LAT
        self.web.page().runJavaScript(
            "window.selectedLat",
            0,
            self._on_lat_received
        )

    def _on_lat_received(self, lat):
        if lat is None:
            QMessageBox.warning(
                self,
                "Ubicación no seleccionada",
                "Haz clic en el mapa para seleccionar una ubicación."
            )
            return

        self._lat = float(lat)

        # 2️⃣ Pedir LON
        self.web.page().runJavaScript(
            "window.selectedLon",
            0,
            self._on_lon_received
        )

    def _on_lon_received(self, lon):
        if lon is None:
            QMessageBox.warning(
                self,
                "Ubicación no seleccionada",
                "Haz clic en el mapa para seleccionar una ubicación."
            )
            return

        self._lon = float(lon)

        # 3️⃣ Guardar
        save_location(
            city="Ubicación personalizada",
            lat=self._lat,
            lon=self._lon
        )

        self.location_selected.emit()
        self.close()
