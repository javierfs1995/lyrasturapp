import sys
import traceback

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QColor, QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

# 🔴 CRÍTICO PARA QtWebEngine (ANTES de QApplication)
QGuiApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

from ui.main_window import MainWindow  # noqa: E402


def excepthook(exc_type, exc_value, exc_tb):
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(msg)

    QMessageBox.critical(
        None,
        "Error crítico",
        msg
    )


def start_main():
    sys.excepthook = excepthook

    app = QApplication(sys.argv)

    # ───────────────── Splash ─────────────────
    pixmap = QPixmap(500, 300)
    pixmap.fill(QColor("#0f1114"))

    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()

    splash.showMessage(
        "Cargando interfaz…",
        Qt.AlignBottom | Qt.AlignCenter,
        QColor("#cfd6dd")
    )
    app.processEvents()

    # ─────────────── Carga real ───────────────
    def load():
        try:
            window = MainWindow()
            window.show()
            splash.finish(window)
        except Exception:
            excepthook(*sys.exc_info())

    # Pequeño delay para que Qt termine de inicializar gráficos
    QTimer.singleShot(300, load)

    sys.exit(app.exec())


if __name__ == "__main__":
    start_main()
