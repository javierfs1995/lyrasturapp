import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl

app = QApplication(sys.argv)
view = QWebEngineView()
view.resize(1000, 700)
view.setUrl(QUrl("https://www.openstreetmap.org"))
view.show()
sys.exit(app.exec())
