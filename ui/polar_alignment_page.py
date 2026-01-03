from __future__ import annotations

import math
import time
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QSlider, QSpinBox, QSizePolicy
)


# ─────────────────────────────────────────────
# Modelo
# ─────────────────────────────────────────────
@dataclass
class PolarSolution:
    error_arcmin: float = 8.0
    alt_arcmin: float = +3.0
    az_arcmin: float = -2.5
    hint: str = "Pulsa “Iniciar ajuste” para comenzar"


def _error_color(err_arcmin: float) -> QColor:
    # Estilo tipo NINA: rojo -> ámbar -> verde
    if err_arcmin <= 2.0:
        return QColor("#2fd27a")   # verde
    if err_arcmin <= 5.0:
        return QColor("#f4b000")   # ámbar
    return QColor("#ff4d4d")       # rojo


def _arrow_head(p: QPainter, tip: QPointF, direction: QPointF, color: QColor):
    """Pinta una punta de flecha simple en 'tip' mirando en 'direction' (unitaria en ejes)."""
    p.save()
    pen = QPen(color, 3)
    pen.setCosmetic(True)
    p.setPen(pen)

    dx, dy = direction.x(), direction.y()
    size = 10
    if abs(dx) > 0:
        p.drawLine(tip, QPointF(tip.x() - dx * size, tip.y() - size))
        p.drawLine(tip, QPointF(tip.x() - dx * size, tip.y() + size))
    else:
        p.drawLine(tip, QPointF(tip.x() - size, tip.y() - dy * size))
        p.drawLine(tip, QPointF(tip.x() + size, tip.y() - dy * size))
    p.restore()


# ─────────────────────────────────────────────
# Widget central: LiveView + Overlay (NINA-like)
# ─────────────────────────────────────────────
class PolarLiveView(QWidget):
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(720, 460)

        self._frame: QImage | None = None
        self._sol = PolarSolution()

        # overlay options
        self.show_circle = True
        self.circle_radius_ratio = 0.22  # relativo al lado menor

    def set_frame(self, img: QImage | None):
        self._frame = img
        self.update()

    def set_solution(self, sol: PolarSolution):
        self._sol = sol
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0b0d10"))  # negro suave tipo NINA

        rect = QRectF(self.rect())

        # Dibuja frame escalado si hay
        img_rect = rect
        if self._frame and not self._frame.isNull():
            pix = QPixmap.fromImage(self._frame)
            scaled = pix.scaled(
                int(rect.width()),
                int(rect.height()),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            x = (rect.width() - scaled.width()) / 2
            y = (rect.height() - scaled.height()) / 2
            p.drawPixmap(QPointF(x, y), scaled)
            img_rect = QRectF(x, y, scaled.width(), scaled.height())
        else:
            self._draw_placeholder(p, rect)

        self._draw_overlay(p, img_rect)

        p.end()

    def _draw_placeholder(self, p: QPainter, rect: QRectF):
        p.save()
        p.setPen(QPen(QColor("#23262d"), 1))
        p.drawRoundedRect(rect.adjusted(14, 14, -14, -14), 12, 12)
        p.setPen(QColor("#8b95a3"))
        f = QFont("Segoe UI")
        f.setPointSize(11)
        p.setFont(f)
        p.drawText(rect, Qt.AlignCenter, "Live View\n(sin cámara: modo demo)")
        p.restore()

    def _draw_overlay(self, p: QPainter, rect: QRectF):
        p.save()

        cx = rect.center().x()
        cy = rect.center().y()
        w = rect.width()
        h = rect.height()
        m = min(w, h)

        # Crosshair
        cross_pen = QPen(QColor("#cfd6dd"), 1)
        cross_pen.setCosmetic(True)
        p.setPen(cross_pen)
        p.drawLine(QPointF(cx - w * 0.5, cy), QPointF(cx + w * 0.5, cy))
        p.drawLine(QPointF(cx, cy - h * 0.5), QPointF(cx, cy + h * 0.5))

        # Círculo
        if self.show_circle:
            r = m * self.circle_radius_ratio
            ring_pen = QPen(QColor("#4fa3ff"), 1)
            ring_pen.setCosmetic(True)
            p.setPen(ring_pen)
            p.drawEllipse(QPointF(cx, cy), r, r)

        # Flechas (ALT/AZ)
        sol = self._sol
        col = _error_color(sol.error_arcmin)

        mag = max(0.0, min(1.0, sol.error_arcmin / 20.0))
        L = 40 + 80 * mag

        arrow_pen = QPen(col, 3)
        arrow_pen.setCosmetic(True)
        p.setPen(arrow_pen)

        # AZ horizontal
        if abs(sol.az_arcmin) > 0.05:
            dirx = 1 if sol.az_arcmin > 0 else -1
            x2 = cx + dirx * L
            p.drawLine(QPointF(cx, cy), QPointF(x2, cy))
            _arrow_head(p, QPointF(x2, cy), QPointF(dirx, 0), col)

        # ALT vertical (pantalla: y hacia abajo)
        if abs(sol.alt_arcmin) > 0.05:
            diry = -1 if sol.alt_arcmin > 0 else 1
            y2 = cy + diry * L
            p.drawLine(QPointF(cx, cy), QPointF(cx, y2))
            _arrow_head(p, QPointF(cx, y2), QPointF(0, diry), col)

        # HUD arriba-izq (semi-transparente)
        pad = 10
        box = QRectF(rect.left() + 14, rect.top() + 14, 320, 92)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawRoundedRect(box, 10, 10)

        p.setPen(QColor("#ffffff"))
        f1 = QFont("Segoe UI")
        f1.setPointSize(10)
        f1.setBold(True)
        p.setFont(f1)
        p.drawText(QRectF(box.left() + pad, box.top() + 8, box.width() - 2 * pad, 22),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   f"Error polar: {sol.error_arcmin:.2f}′")

        f2 = QFont("Segoe UI")
        f2.setPointSize(9)
        p.setFont(f2)
        p.setPen(QColor("#cfd6dd"))
        p.drawText(QRectF(box.left() + pad, box.top() + 32, box.width() - 2 * pad, 18),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   f"ALT: {sol.alt_arcmin:+.2f}′   AZ: {sol.az_arcmin:+.2f}′")

        p.setPen(QColor("#8b95a3"))
        p.drawText(QRectF(box.left() + pad, box.top() + 52, box.width() - 2 * pad, 30),
                   Qt.AlignLeft | Qt.AlignVCenter,
                   sol.hint)

        p.restore()


# ─────────────────────────────────────────────
# Página: NINA-like + Semi-en vivo
# ─────────────────────────────────────────────
class PolarAlignmentPage(QWidget):
    """
    Polar Alignment NINA-like con modo semi-en vivo:
    - Vista grande con overlay
    - Panel derecho con estado/controles
    - Timer que actualiza solución (demo ahora, solver real después)
    """
    def __init__(self):
        super().__init__()

        self._sol = PolarSolution(
            error_arcmin=8.0,
            alt_arcmin=+3.0,
            az_arcmin=-2.5,
            hint="Ajusta ALT/AZ para minimizar el error"
        )
        self._running = False
        self._last_t = time.time()

        self._build_ui()

        # Semi-en vivo (por defecto ~1 Hz)
        self.timer = QTimer(self)
        self.timer.setInterval(800)
        self.timer.timeout.connect(self._tick_demo)

        # Demo frame (para ver algo bonito)
        self._set_demo_frame()

        # Refresca panel
        self._refresh_panel()

    # ─────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # Centro: live view
        self.view = PolarLiveView()
        self.view.set_solution(self._sol)
        root.addWidget(self.view, 1)

        # Derecha: panel (tipo NINA)
        side = QFrame()
        side.setFixedWidth(340)
        side.setObjectName("PolarSidePanel")
        side.setStyleSheet("""
            QFrame#PolarSidePanel {
                background:#171a20;
                border: 1px solid #23262d;
                border-radius: 12px;
            }
        """)

        side_l = QVBoxLayout(side)
        side_l.setContentsMargins(14, 14, 14, 14)
        side_l.setSpacing(10)

        title = QLabel("Polar Alignment")
        title.setStyleSheet("font-size:14px; font-weight:700; color:#e6e6e6;")
        side_l.addWidget(title)

        self.lbl_status = QLabel("Listo. Inicia el ajuste continuo.")
        self.lbl_status.setStyleSheet("color:#8b95a3;")
        side_l.addWidget(self.lbl_status)

        self.lbl_error_big = QLabel("—")
        self.lbl_error_big.setStyleSheet("font-size:28px; font-weight:800;")
        side_l.addWidget(self.lbl_error_big)

        self.lbl_dirs = QLabel("—")
        self.lbl_dirs.setStyleSheet("color:#cfd6dd; font-size:12px;")
        self.lbl_dirs.setWordWrap(True)
        side_l.addWidget(self.lbl_dirs)

        # Botones
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ Iniciar ajuste")
        self.btn_stop = QPushButton("⏹ Detener")
        self.btn_stop.setEnabled(False)

        self.btn_start.clicked.connect(self.start_continuous)
        self.btn_stop.clicked.connect(self.stop_continuous)

        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        side_l.addLayout(btn_row)

        # Intervalo semi-en vivo
        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Actualización"))
        self.rate_slider = QSlider(Qt.Horizontal)
        self.rate_slider.setRange(250, 1500)
        self.rate_slider.setValue(800)
        self.rate_slider.valueChanged.connect(self._on_rate_change)
        rate_row.addWidget(self.rate_slider)

        self.rate_lbl = QLabel("800 ms")
        self.rate_lbl.setStyleSheet("color:#8b95a3;")
        rate_row.addWidget(self.rate_lbl)
        side_l.addLayout(rate_row)

        # Objetivo
        thr_row = QHBoxLayout()
        thr_row.addWidget(QLabel("Objetivo"))
        self.thr_spin = QSpinBox()
        self.thr_spin.setRange(1, 10)
        self.thr_spin.setValue(2)
        self.thr_spin.setSuffix("′")
        thr_row.addWidget(self.thr_spin)
        thr_row.addStretch()
        side_l.addLayout(thr_row)

        side_l.addStretch()

        hint = QLabel(
            "Modo semi-en vivo: la solución se actualiza cada X ms.\n"
            "Luego conectaremos solver real + live view ZWO sin rehacer la UI."
        )
        hint.setStyleSheet("color:#6b7483; font-size:11px;")
        hint.setWordWrap(True)
        side_l.addWidget(hint)

        root.addWidget(side)

    # ─────────────────────────
    # API pública (para solver real / cámara real)
    def set_frame(self, img: QImage | None):
        self.view.set_frame(img)

    def set_solution(self, error_arcmin: float, alt_arcmin: float, az_arcmin: float, hint: str = ""):
        self._sol.error_arcmin = float(error_arcmin)
        self._sol.alt_arcmin = float(alt_arcmin)
        self._sol.az_arcmin = float(az_arcmin)
        if hint:
            self._sol.hint = hint
        self.view.set_solution(self._sol)
        self._refresh_panel()

    # ─────────────────────────
    def start_continuous(self):
        if self._running:
            return
        self._running = True
        self._last_t = time.time()
        self.timer.start()
        self.lbl_status.setText("Ajuste continuo activo (semi-en vivo)…")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_continuous(self):
        if not self._running:
            return
        self._running = False
        self.timer.stop()
        self.lbl_status.setText("Pausado.")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _on_rate_change(self, v: int):
        self.timer.setInterval(v)
        self.rate_lbl.setText(f"{v} ms")

    # ─────────────────────────
    # Demo: simula convergencia (para ver UI ya)
    def _tick_demo(self):
        dt = time.time() - self._last_t
        self._last_t = time.time()

        err = self._sol.error_arcmin
        if err > 0.2:
            err = max(0.0, err - 0.35 * (dt * 1.5))

        noise = 0.08 * math.sin(time.time() * 2.0)

        alt = self._sol.alt_arcmin * 0.92 + noise
        az = self._sol.az_arcmin * 0.92 - noise

        target = float(self.thr_spin.value())
        hint = "Ajusta ALT/AZ para minimizar el error"
        if err <= target:
            hint = "✅ Alineación correcta. Puedes detener."

        self.set_solution(err + abs(noise) * 0.1, alt, az, hint)

    def _refresh_panel(self):
        err = self._sol.error_arcmin
        col = _error_color(err)

        self.lbl_error_big.setText(f"{err:.2f}′")
        self.lbl_error_big.setStyleSheet(
            f"font-size:28px; font-weight:800; color:{col.name()};"
        )

        az_dir = "→" if self._sol.az_arcmin > 0.05 else ("←" if self._sol.az_arcmin < -0.05 else "·")
        alt_dir = "↑" if self._sol.alt_arcmin > 0.05 else ("↓" if self._sol.alt_arcmin < -0.05 else "·")

        self.lbl_dirs.setText(
            f"Corrección sugerida:\n"
            f"AZ {az_dir}  ({self._sol.az_arcmin:+.2f}′)\n"
            f"ALT {alt_dir} ({self._sol.alt_arcmin:+.2f}′)"
        )

    def _set_demo_frame(self):
        # Imagen demo de “estrellas” para que se vea pro
        w, h = 1280, 720
        img = QImage(w, h, QImage.Format_RGB32)
        img.fill(QColor("#07080a"))

        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)

        for i in range(240):
            x = int((i * 97) % w)
            y = int((i * 53) % h)
            r = 1 + (i % 2)
            a = 80 + (i % 150)
            p.setBrush(QColor(220, 230, 255, a))
            p.drawEllipse(QPointF(x, y), r, r)

        p.end()
        self.set_frame(img)
