from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView


class RadarWidget(QWidget):
    def __init__(self, lat: float, lon: float, overlay: str = "clouds"):
        super().__init__()

        self.lat = lat
        self.lon = lon
        self.overlay = overlay

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web = QWebEngineView()
        layout.addWidget(self.web)

        self.load()

    def load(self):
        url = (
            "https://embed.windy.com/embed2.html?"
            f"lat={self.lat}&lon={self.lon}"
            "&zoom=6"
            "&level=surface"
            f"&overlay={self.overlay}"
            "&product=ecmwf"
            "&menu=&message=&marker=&calendar=&pressure=&type=map"
            "&location=coordinates"
            "&metricWind=default&metricTemp=default"
        )

        self.web.setUrl(QUrl(url))

    def set_overlay(self, overlay: str):
        self.overlay = overlay
        self.load()
