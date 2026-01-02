from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
import math

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QPen, QFont, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame
)

from ui.components.card import Card
from astronomy.polar import polaris_position


class PolarDial(QWidget):
    """
    Dial tipo visor polar (pero útil también sin visor: te da orientación “reloj”).
    - 12 arriba
    - sentido horario
    """
    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 320)
        self.angle_deg = 0.0

    def set_angle(self, angle_deg: float):
        self.angle_deg = float(angle_deg) % 360.0
        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        s = min(w, h)
        cx, cy = w / 2, h / 2
        r = s * 0.43
        orbit_r = s * 0.30

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Outer circle
        pen_outer = QPen(Qt.gray)
        pen_outer.setWidth(2)
        p.setPen(pen_outer)
        p.drawEllipse(int(cx - r), int(cy - r), int(2 * r), int(2 * r))

        # Crosshair
        pen_cross = QPen(Qt.darkGray)
        pen_cross.setWidth(1)
        p.setPen(pen_cross)
        p.drawLine(int(cx - r), int(cy), int(cx + r), int(cy))
        p.drawLine(int(cx), int(cy - r), int(cx), int(cy + r))

        # Orbit
        pen_orbit = QPen(Qt.darkGray)
        pen_orbit.setWidth(2)
        p.setPen(pen_orbit)
        p.drawEllipse(int(cx - orbit_r), int(cy - orbit_r), int(2 * orbit_r), int(2 * orbit_r))

        # 12/3/6/9
        p.setPen(Qt.gray)
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        p.setFont(f)
        p.drawText(int(cx - 10), int(cy - r - 8), "12")
        p.drawText(int(cx + r - 12), int(cy + 4), "3")
        p.drawText(int(cx - 6), int(cy + r + 16), "6")
        p.drawText(int(cx - r - 18), int(cy + 4), "9")

        # Polaris dot
        theta = math.radians(self.angle_deg)
        x = cx + orbit_r * math.sin(theta)
        y = cy - orbit_r * math.cos(theta)

        pen_dot = QPen(Qt.white)
        pen_dot.setWidth(8)
        p.setPen(pen_dot)
        p.drawPoint(int(x), int(y))

        # Center pole
        pen_center = QPen(Qt.darkGray)
        pen_center.setWidth(6)
        p.setPen(pen_center)
        p.drawPoint(int(cx), int(cy))

        p.end()


class EqMountDiagram(QWidget):
    """
    Diagrama simplificado de una montura EQ (EQ-1/EQ-2 style):
    - trípode
    - cabeza de montura
    - eje RA apuntando al norte
    - tornillo ALT (sube/baja)
    - tornillos AZI (izq/der)
    Es visual: NO controla nada.
    """
    def __init__(self):
        super().__init__()
        self.setMinimumSize(260, 260)
        self.lat_target_deg = 0.0
        self.polar_clock_text = "—"

    def set_targets(self, lat_deg: float, clock_text: str):
        self.lat_target_deg = float(lat_deg)
        self.polar_clock_text = clock_text
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        w, h = self.width(), self.height()
        cx = w * 0.52
        base_y = h * 0.85

        # Colors (neutral, acorde tema oscuro)
        pen_main = QPen(Qt.gray)
        pen_main.setWidth(2)

        pen_soft = QPen(Qt.darkGray)
        pen_soft.setWidth(2)

        p.setPen(pen_main)

        # Tripod (3 legs)
        p.drawLine(int(cx), int(base_y - 140), int(cx - 90), int(base_y))
        p.drawLine(int(cx), int(base_y - 140), int(cx + 90), int(base_y))
        p.drawLine(int(cx), int(base_y - 140), int(cx), int(base_y))

        # Mount head (box)
        head = QRectF(cx - 40, base_y - 165, 80, 45)
        p.setPen(pen_soft)
        p.setBrush(QBrush(Qt.transparent))
        p.drawRoundedRect(head, 10, 10)

        # RA axis (tilted line pointing "north")
        p.setPen(pen_main)
        ra_x1, ra_y1 = cx + 10, base_y - 160
        ra_x2, ra_y2 = cx + 85, base_y - 230
        p.drawLine(int(ra_x1), int(ra_y1), int(ra_x2), int(ra_y2))

        # N label + arrow
        p.setPen(Qt.gray)
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        p.setFont(f)
        p.drawText(int(ra_x2 + 6), int(ra_y2 - 6), "N")

        # ALT screw indicator (up/down)
        p.setPen(pen_soft)
        alt_x = cx - 55
        alt_y = base_y - 150
        p.drawLine(int(alt_x), int(alt_y), int(alt_x), int(alt_y + 65))
        p.drawLine(int(alt_x - 8), int(alt_y + 10), int(alt_x), int(alt_y))
        p.drawLine(int(alt_x + 8), int(alt_y + 10), int(alt_x), int(alt_y))
        p.drawLine(int(alt_x - 8), int(alt_y + 55), int(alt_x), int(alt_y + 65))
        p.drawLine(int(alt_x + 8), int(alt_y + 55), int(alt_x), int(alt_y + 65))

        # AZ bolts indicator (left/right)
        p.setPen(pen_soft)
        azi_y = base_y - 115
        p.drawLine(int(cx - 90), int(azi_y), int(cx + 90), int(azi_y))
        # arrow heads
        p.drawLine(int(cx - 80), int(azi_y - 8), int(cx - 90), int(azi_y))
        p.drawLine(int(cx - 80), int(azi_y + 8), int(cx - 90), int(azi_y))
        p.drawLine(int(cx + 80), int(azi_y - 8), int(cx + 90), int(azi_y))
        p.drawLine(int(cx + 80), int(azi_y + 8), int(cx + 90), int(azi_y))

        # Labels
        p.setPen(Qt.gray)
        f2 = QFont()
        f2.setPointSize(9)
        f2.setBold(True)
        p.setFont(f2)
        p.drawText(int(cx - 120), int(alt_y - 8), "ALT ↑/↓")
        p.drawText(int(cx - 55), int(azi_y - 10), "AZI ←/→")

        # Target text block
        p.setPen(Qt.gray)
        f3 = QFont()
        f3.setPointSize(9)
        f3.setBold(False)
        p.setFont(f3)

        p.drawText(10, 20, f"Altitud objetivo ≈ {self.lat_target_deg:.1f}°")
        p.drawText(10, 38, f"Polaris (reloj) ≈ {self.polar_clock_text}")

        p.end()


class PolarAlignmentPage(QWidget):
    def __init__(self, location: dict, tz_name: str = "Europe/Madrid"):
        super().__init__()
        self.location = location or {}
        self.tz = ZoneInfo(tz_name)

        # En tu caso: NO visor polar
        self.has_polar_scope = False

        root = QHBoxLayout(self)
        root.setSpacing(16)

        # ── Left: Dial + compact info ─────────────────────────────
        left = Card()
        left.layout.setSpacing(10)

        title = QLabel("🧭 Polar Alignment (sin visor polar)")
        title.setObjectName("Title")
        left.layout.addWidget(title)

        subtitle = QLabel("Objetivo: apuntar el eje RA al polo norte celeste lo mejor posible (manual).")
        subtitle.setStyleSheet("color:#9fb0ba;")
        left.layout.addWidget(subtitle)

        dial_row = QHBoxLayout()
        dial_row.setSpacing(16)

        self.dial = PolarDial()
        dial_row.addWidget(self.dial, 2)

        quick = QVBoxLayout()
        quick.setSpacing(10)

        self.card_polaris = self.small_info_card("⭐ Polaris (reloj)", "—")
        self.card_lat = self.small_info_card("📐 Altitud objetivo", "—")
        self.card_action = self.small_info_card("🎯 Qué mover ahora", "Ajusta ALT ≈ latitud y AZI hacia el norte.")

        quick.addWidget(self.card_polaris)
        quick.addWidget(self.card_lat)
        quick.addWidget(self.card_action)
        quick.addStretch()

        dial_row.addLayout(quick, 1)
        left.layout.addLayout(dial_row)

        self.meta_lbl = QLabel("")
        self.meta_lbl.setStyleSheet("color:#9fb0ba; font-size:9pt;")
        left.layout.addWidget(self.meta_lbl)

        btns = QHBoxLayout()
        self.btn_now = QPushButton("Actualizar")
        self.btn_now.setCursor(Qt.PointingHandCursor)
        self.btn_now.clicked.connect(self.update_polar)
        self.btn_now.setStyleSheet("""
            QPushButton {
                background-color: #1f272c;
                border: 1px solid #2a353c;
                border-radius: 10px;
                padding: 8px 12px;
                color: #f2f6f8;
                font-weight: 800;
            }
            QPushButton:hover { background-color: #26323a; }
        """)
        btns.addWidget(self.btn_now)
        btns.addStretch()
        left.layout.addLayout(btns)

        # ── Right: Diagram + steps ───────────────────────────────
        right = Card()
        right.layout.setSpacing(10)

        rtitle = QLabel("🧩 Diagrama EQ (qué mover)")
        rtitle.setObjectName("Title")
        right.layout.addWidget(rtitle)

        self.eq_diagram = EqMountDiagram()
        right.layout.addWidget(self.eq_diagram)

        steps_title = QLabel("✅ Pasos recomendados (sin visor polar)")
        steps_title.setStyleSheet("color:#9fb0ba; font-weight:900; margin-top:6px;")
        right.layout.addWidget(steps_title)

        steps = [
            "1) Nivela el trípode (crítico).",
            "2) ALT: ajusta la escala a tu latitud (aprox.).",
            "3) AZI: orienta la montura al norte (brújula + corrige a ojo hacia Polaris).",
            "4) Busca Polaris con el buscador o ocular de baja potencia.",
            "5) Centra Polaris y afina ALT/AZI en pequeños pasos.",
            "6) (Mejora extra) Drift alignment rápido en una estrella (lo añadiremos).",
        ]
        for s in steps:
            lbl = QLabel(s)
            lbl.setStyleSheet("color:#d7e0e5; font-weight:700;")
            right.layout.addWidget(lbl)

        zwo = QLabel("📷 Próximo (ZWO): Live View + asistente visual para error polar (sin GoTo).")
        zwo.setStyleSheet("color:#7f96a2; font-size:9pt; margin-top:6px;")
        right.layout.addWidget(zwo)

        root.addWidget(left, 3)
        root.addWidget(right, 2)

        # Timer
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_polar)
        self.timer.start()

        self.update_polar()

    # ─────────────────────────────────────────────
    # Small info card helper
    # ─────────────────────────────────────────────
    def small_info_card(self, title: str, value: str):
        c = QFrame()
        c.setObjectName("SmallCard")
        c.setStyleSheet("""
            QFrame#SmallCard {
                background-color: #1f272c;
                border: 1px solid #2a353c;
                border-radius: 12px;
            }
        """)
        lay = QVBoxLayout(c)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        t = QLabel(title)
        t.setStyleSheet("color:#9fb0ba; font-weight:900; font-size:9pt;")
        v = QLabel(value)
        v.setStyleSheet("color:#f2f6f8; font-weight:900; font-size:12pt;")
        lay.addWidget(t)
        lay.addWidget(v)
        return c

    def set_small_card_value(self, card: QFrame, value: str):
        lay = card.layout()
        if lay and lay.count() >= 2:
            w = lay.itemAt(1).widget()
            if isinstance(w, QLabel):
                w.setText(value)

    def set_location(self, location: dict):
        self.location = location or {}
        self.update_polar()

    def update_polar(self):
        lat = float(self.location.get("lat", 0.0))
        lon = float(self.location.get("lon", 0.0))
        name = (self.location.get("name") or "Ubicación").strip()

        now_local = datetime.now(self.tz)
        pos = polaris_position(now_local, lon_deg=lon)

        # Dial
        self.dial.set_angle(pos.reticle_angle_deg)

        # Clock text
        total_minutes = int(round(pos.clock_hours * 60)) % (12 * 60)
        hh = total_minutes // 60
        mm = total_minutes % 60
        if hh == 0:
            hh = 12
        clock_txt = f"{hh:02d}:{mm:02d}"

        self.set_small_card_value(self.card_polaris, clock_txt)
        self.set_small_card_value(self.card_lat, f"ALT ≈ {lat:.1f}°")

        # Acción sugerida (sin visor polar: enfoque en ALT/AZI)
        self.set_small_card_value(
            self.card_action,
            "1) ALT ≈ latitud  2) AZI hacia Polaris  3) Centra Polaris y afina"
        )

        self.eq_diagram.set_targets(lat_deg=lat, clock_text=clock_txt)

        self.meta_lbl.setText(
            f"{name}  |  Lat {lat:.4f}  Lon {lon:.4f}  |  Hora local {now_local.strftime('%Y-%m-%d %H:%M:%S')} ({self.tz.key})"
        )
