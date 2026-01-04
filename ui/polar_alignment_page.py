# ui/polar_alignment_page.py
# Polar Alignment (NINA-style) with stable overlay using QGraphicsView
# - Works with FrameBus (camera/frame_bus.py) or falls back to demo mode
# - Avoids "QObject initialized twice" by reusing a singleton bus instance
# - Handles grayscale (HxW) and color (HxWx3/4) frames
# - Keeps bottom error panel always visible (Az / Alt / Total)

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from PySide6.QtCore import Qt, QRectF, QTimer, QSize
from PySide6.QtGui import (
    QImage,
    QPixmap,
    QPen,
    QBrush,
    QColor,
    QFont,
)
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QComboBox,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsSimpleTextItem,
    QSizePolicy,
)

# ─────────────────────────────────────────────
# Polaris confirmation constants
# ─────────────────────────────────────────────
POLARIS_CONFIRM_FRAMES = 8          # ADDED: frames needed to confirm
POLARIS_CONFIRM_RADIUS_PX = 6.0     # ADDED: max movement between frames (px)


# ─────────────────────────────────────────────
# FrameBus safe import / singleton accessor
# ─────────────────────────────────────────────
def _get_frame_bus():
    """
    Your project already has camera/frame_bus.py.
    Different versions may expose:
      - FrameBus() as a singleton QObject (calling twice crashes)
      - get_bus() / instance()
    This function tries to obtain ONE shared instance safely.
    """
    try:
        # common: from camera.frame_bus import FrameBus
        from camera.frame_bus import FrameBus  # type: ignore

        # If it has an instance() method (classic singleton)
        if hasattr(FrameBus, "instance") and callable(getattr(FrameBus, "instance")):
            return FrameBus.instance()

        # If FrameBus is designed as a singleton class that errors on double init,
        # it may keep a module-level instance like FrameBus._instance
        if hasattr(FrameBus, "_instance"):
            inst = getattr(FrameBus, "_instance")
            if inst is not None:
                return inst

        # Fallback: try to reuse a cached global in this module
        global _FRAME_BUS_SINGLETON
        if "_FRAME_BUS_SINGLETON" in globals() and _FRAME_BUS_SINGLETON is not None:
            return _FRAME_BUS_SINGLETON

        _FRAME_BUS_SINGLETON = FrameBus()
        return _FRAME_BUS_SINGLETON

    except Exception:
        return None


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _qimage_from_ndarray(frame: np.ndarray) -> QImage:
    """
    Accepts:
      - grayscale HxW uint8/uint16/float
      - RGB/RGBA HxWx3/4 uint8
    Returns a QImage that is safe to convert to QPixmap.
    """
    if frame is None:
        return QImage()

    arr = frame
    if not isinstance(arr, np.ndarray):
        return QImage()

    # Normalize types
    if arr.dtype != np.uint8:
        # scale to 0..255
        a = arr.astype(np.float32)
        a -= float(np.min(a)) if a.size else 0.0
        mx = float(np.max(a)) if a.size else 1.0
        if mx <= 0:
            mx = 1.0
        a = (a / mx) * 255.0
        arr = np.clip(a, 0, 255).astype(np.uint8)

    if arr.ndim == 2:
        h, w = arr.shape
        # grayscale
        qimg = QImage(arr.data, w, h, w, QImage.Format_Grayscale8)
        return qimg.copy()  # detach from numpy memory
    elif arr.ndim == 3:
        h, w, ch = arr.shape
        if ch == 3:
            qimg = QImage(arr.data, w, h, w * 3, QImage.Format_RGB888)
            return qimg.copy()
        if ch == 4:
            qimg = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888)
            return qimg.copy()

    return QImage()


def _clamp(v: float, a: float, b: float) -> float:
    return max(a, min(b, v))


def _dist(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _centroid_brightest(
    img: np.ndarray,
    seed: Optional[Tuple[float, float]] = None,
    search_radius: int = 120,
) -> Optional[Tuple[float, float]]:
    """
    Robust enough for Polaris-like field:
    - if seed exists: search in a window around seed (stabilizes point)
    - else: search whole image
    Returns (x, y) centroid of brightest blob-ish region.
    """
    if img is None or not isinstance(img, np.ndarray) or img.size == 0:
        return None

    # ensure grayscale float
    if img.ndim == 3:
        img_g = img[..., 0].astype(np.float32)
    else:
        img_g = img.astype(np.float32)

    h, w = img_g.shape[:2]

    if seed is not None:
        cx, cy = int(seed[0]), int(seed[1])
        x0 = int(_clamp(cx - search_radius, 0, w - 1))
        x1 = int(_clamp(cx + search_radius, 0, w - 1))
        y0 = int(_clamp(cy - search_radius, 0, h - 1))
        y1 = int(_clamp(cy + search_radius, 0, h - 1))
        roi = img_g[y0 : y1 + 1, x0 : x1 + 1]
        if roi.size == 0:
            return None
        # brightest pixel
        iy, ix = np.unravel_index(int(np.argmax(roi)), roi.shape)
        px = x0 + ix
        py = y0 + iy
    else:
        py, px = np.unravel_index(int(np.argmax(img_g)), img_g.shape)

    # small window around the peak for centroid
    win = 18
    x0 = int(_clamp(px - win, 0, w - 1))
    x1 = int(_clamp(px + win, 0, w - 1))
    y0 = int(_clamp(py - win, 0, h - 1))
    y1 = int(_clamp(py + win, 0, h - 1))
    patch = img_g[y0 : y1 + 1, x0 : x1 + 1]
    if patch.size == 0:
        return None

    # threshold relative to peak
    peak = float(np.max(patch))
    if peak <= 0:
        return None

    thr = peak * 0.60
    mask = patch >= thr
    if not np.any(mask):
        return float(px), float(py)

    yy, xx = np.nonzero(mask)
    weights = patch[yy, xx]
    s = float(np.sum(weights))
    if s <= 0:
        return float(px), float(py)

    cx = float(np.sum((x0 + xx) * weights) / s)
    cy = float(np.sum((y0 + yy) * weights) / s)
    return cx, cy


# ─────────────────────────────────────────────
# Simple error model (semi-live)
# ─────────────────────────────────────────────
@dataclass
class AlignmentState:
    # reference center in image coordinates (target circle center)
    center: Tuple[float, float] = (0.0, 0.0)
    # detected polaris in image coordinates
    polaris: Optional[Tuple[float, float]] = None
    # smoothed polaris
    polaris_s: Optional[Tuple[float, float]] = None
    # last frame timestamp
    last_t: float = 0.0
    # pixels -> arcmin (rough). You can calibrate later with plate solve.
    arcsec_per_px: float = 2.0  # default; editable in UI

    # ────────────────
    # Polaris confirmation (ADDED)
    # ────────────────
    polaris_confirmed: bool = False
    confirm_count: int = 0
    last_confirm_pos: Optional[Tuple[float, float]] = None


# ─────────────────────────────────────────────
# Main Page
# ─────────────────────────────────────────────
class PolarAlignmentPage(QWidget):
    """
    NINA-like Polar Alignment:
    - Left: options & status
    - Center: live view with overlay (circle + crosshair + polaris point + arrows)
    - Bottom: AZ / ALT / TOTAL panels always visible
    """

    def __init__(self):
        super().__init__()

        self.state = AlignmentState()
        self._last_frame: Optional[np.ndarray] = None

        self._bus = _get_frame_bus()

        self._build_ui()
        self._wire()

        # If bus exists, connect once
        if self._bus is not None and hasattr(self._bus, "frame_ready"):
            # Prevent double connections when recreating widget
            try:
                self._bus.frame_ready.disconnect(self.on_new_frame)  # type: ignore
            except Exception:
                pass
            self._bus.frame_ready.connect(self.on_new_frame)  # type: ignore

        # overlay refresh timer (keeps stable UI even if frames come slower)
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._tick_ui)
        self.ui_timer.start(100)  # 10 fps for UI overlay

        # demo timer
        self.demo_timer = QTimer(self)
        self.demo_timer.timeout.connect(self._demo_step)

        self._set_status("Esperando Live View…")

    # ─────────────────────────
    # UI
    # ─────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # top split: left + center + right (like NINA)
        top = QHBoxLayout()
        top.setSpacing(12)

        # LEFT PANEL
        self.left_panel = self._card()
        self.left_panel.setFixedWidth(320)
        lp = QVBoxLayout(self.left_panel)
        lp.setContentsMargins(12, 12, 12, 12)
        lp.setSpacing(10)

        t = QLabel("Three Point Polar Alignment")
        t.setObjectName("CardTitle")
        t.setStyleSheet("font-weight:700; font-size:13px;")
        lp.addWidget(t)

        self.lbl_status = QLabel("—")
        self.lbl_status.setStyleSheet("color:#8b95a3;")
        self.lbl_status.setWordWrap(True)
        lp.addWidget(self.lbl_status)

        lp.addSpacing(6)

        row = QHBoxLayout()
        row.addWidget(QLabel("Escala (arcsec/px):"))
        self.cmb_scale = QComboBox()
        self.cmb_scale.addItems(["1.0", "1.5", "2.0", "2.5", "3.0", "4.0"])
        self.cmb_scale.setCurrentText("2.0")
        self.cmb_scale.setFixedWidth(90)
        row.addStretch()
        row.addWidget(self.cmb_scale)
        lp.addLayout(row)

        self.btn_semi_live = QPushButton("▶ Ajuste semi-en vivo")
        self.btn_semi_live.setToolTip("Lee el Live View y actualiza la indicación automáticamente.")
        lp.addWidget(self.btn_semi_live)

        self.btn_capture = QPushButton("📌 Capturar / Re-solucionar")
        self.btn_capture.setToolTip("Fuerza un recalculo usando el frame actual.")
        lp.addWidget(self.btn_capture)

        self.btn_reset = QPushButton("↻ Reiniciar")
        lp.addWidget(self.btn_reset)

        self.btn_demo = QPushButton("🧪 Demo (Polaris simulada)")
        lp.addWidget(self.btn_demo)

        lp.addStretch()

        # CENTER: Live view + overlay scene
        self.view = QGraphicsView()
        self.view.setRenderHints(self.view.renderHints())
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setStyleSheet("background:#0b0d10; border: 1px solid #23262d; border-radius:12px;")

        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)

        # Frame pixmap
        self.frame_item = QGraphicsPixmapItem()
        self.scene.addItem(self.frame_item)

        # Overlay items
        # Target circle (center)
        self.target_circle = QGraphicsEllipseItem()
        self.target_circle.setPen(QPen(QColor("#d050ff"), 2))  # magenta like NINA
        self.target_circle.setBrush(Qt.NoBrush)
        self.scene.addItem(self.target_circle)

        # Crosshair
        self.cross_h = QGraphicsLineItem()
        self.cross_v = QGraphicsLineItem()
        pen_cross = QPen(QColor("#cfd6dd"), 1)
        pen_cross.setCosmetic(True)
        self.cross_h.setPen(pen_cross)
        self.cross_v.setPen(pen_cross)
        self.scene.addItem(self.cross_h)
        self.scene.addItem(self.cross_v)

        # Polaris point
        self.polaris_dot = QGraphicsEllipseItem()
        self.polaris_dot.setPen(QPen(QColor("#ff9a3d"), 2))
        self.polaris_dot.setBrush(QBrush(QColor("#ff9a3d")))
        self.scene.addItem(self.polaris_dot)

        # Arrow lines
        self.az_arrow = QGraphicsLineItem()
        self.alt_arrow = QGraphicsLineItem()
        pen_az = QPen(QColor("#00d6ff"), 3)   # cyan
        pen_alt = QPen(QColor("#ffd44a"), 3)  # yellow
        pen_az.setCosmetic(True)
        pen_alt.setCosmetic(True)
        self.az_arrow.setPen(pen_az)
        self.alt_arrow.setPen(pen_alt)
        self.scene.addItem(self.az_arrow)
        self.scene.addItem(self.alt_arrow)

        # On-frame label (like "Adjust Altitude / Azimuth")
        self.top_hint = QGraphicsSimpleTextItem("Adjust Altitude / Azimuth")
        self.top_hint.setBrush(QBrush(QColor("#cfd6dd")))
        f = QFont("Segoe UI", 11)
        f.setBold(True)
        self.top_hint.setFont(f)
        self.scene.addItem(self.top_hint)

        # RIGHT PANEL placeholder (NINA has sequences etc.)
        self.right_panel = self._card()
        self.right_panel.setFixedWidth(320)
        rp = QVBoxLayout(self.right_panel)
        rp.setContentsMargins(12, 12, 12, 12)
        rp.setSpacing(10)

        rt = QLabel("Info")
        rt.setStyleSheet("font-weight:700;")
        rp.addWidget(rt)
        self.lbl_info = QLabel("Live View: —\nPolaris: —\n")
        self.lbl_info.setStyleSheet("color:#8b95a3;")
        self.lbl_info.setWordWrap(True)
        rp.addWidget(self.lbl_info)
        rp.addStretch()

        top.addWidget(self.left_panel)
        top.addWidget(self.view, 1)
        top.addWidget(self.right_panel)

        # BOTTOM ERROR BAR (always visible)
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self.az_box = self._error_box("Azimuth Error", QColor("#00d6ff"))
        self.alt_box = self._error_box("Altitude Error", QColor("#ffd44a"))
        self.total_box = self._error_box("Total Error", QColor("#ff4a4a"))

        bottom.addWidget(self.az_box["frame"], 1)
        bottom.addWidget(self.alt_box["frame"], 1)
        bottom.addWidget(self.total_box["frame"], 1)

        root.addLayout(top, 1)
        root.addLayout(bottom)

        # Initialize hidden overlay until we get a frame size
        self._set_overlay_visible(False)

    def _card(self) -> QFrame:
        w = QFrame()
        w.setObjectName("Card")
        w.setStyleSheet(
            "QFrame#Card { background:#171a20; border:1px solid #23262d; border-radius:12px; }"
        )
        return w

    def _error_box(self, title: str, color: QColor):
        f = self._card()
        lay = QVBoxLayout(f)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(3)

        t = QLabel(title)
        t.setStyleSheet("color:#cfd6dd; font-weight:700; font-size:12px;")
        lay.addWidget(t)

        big = QLabel("—")
        big.setStyleSheet(f"color:{color.name()}; font-size:28px; font-weight:800;")
        lay.addWidget(big)

        hint = QLabel("—")
        hint.setStyleSheet(f"color:{color.name()}; font-size:16px; font-weight:700;")
        lay.addWidget(hint)

        small = QLabel("—")
        small.setStyleSheet("color:#8b95a3;")
        lay.addWidget(small)

        lay.addStretch()
        return {"frame": f, "big": big, "hint": hint, "small": small}

    # ─────────────────────────
    # Wiring
    # ─────────────────────────
    def _wire(self):
        self.btn_semi_live.clicked.connect(self._toggle_semi_live)
        self.btn_capture.clicked.connect(self._force_solve)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_demo.clicked.connect(self._toggle_demo)
        self.cmb_scale.currentTextChanged.connect(self._on_scale_changed)

    def _on_scale_changed(self, txt: str):
        try:
            self.state.arcsec_per_px = float(txt)
        except Exception:
            self.state.arcsec_per_px = 2.0

    # ─────────────────────────
    # Status / actions
    # ─────────────────────────
    def _set_status(self, txt: str):
        self.lbl_status.setText(txt)

    def _set_overlay_visible(self, vis: bool):
        self.target_circle.setVisible(vis)
        self.cross_h.setVisible(vis)
        self.cross_v.setVisible(vis)
        self.polaris_dot.setVisible(vis)
        self.az_arrow.setVisible(vis)
        self.alt_arrow.setVisible(vis)
        self.top_hint.setVisible(vis)

    def _toggle_demo(self):
        if self.demo_timer.isActive():
            self.demo_timer.stop()
            self.btn_demo.setText("🧪 Demo (Polaris simulada)")
            self._set_status("Demo detenida. Esperando Live View…")
            return

        self.demo_timer.start(120)  # ~8 fps
        self.btn_demo.setText("⏸ Detener demo")
        self._set_status("Demo activa: generando frames de Polaris…")

    def _toggle_semi_live(self):
        # Semi-live is simply "keep solving as frames arrive"
        # We'll use a flag; actual processing happens in on_new_frame + _tick_ui
        self._semi_live = not getattr(self, "_semi_live", False)
        self.btn_semi_live.setText("⏸ Pausar semi-en vivo" if self._semi_live else "▶ Ajuste semi-en vivo")
        self._set_status("Semi-en vivo activo: analizando Live View…" if self._semi_live else "Semi-en vivo pausado.")

    def _force_solve(self):
        # Solve once from the last frame
        if self._last_frame is None:
            self._set_status("No hay frame aún. Activa el Live View o la Demo.")
            return
        self._solve_frame(self._last_frame, force=True)

    def _reset(self):
        self.state.polaris = None
        self.state.polaris_s = None

        # ADDED: reset confirmation state
        self.state.polaris_confirmed = False
        self.state.confirm_count = 0
        self.state.last_confirm_pos = None

        self._set_status("Reiniciado. Esperando Live View…")
        self._update_errors(0.0, 0.0)
        self._update_overlay()

    # ─────────────────────────
    # Frame input
    # ─────────────────────────
    def on_new_frame(self, frame):
        """
        FrameBus may emit:
          - numpy array
          - list or bytes (older versions)
        We support numpy arrays. If it's bytes, ignore.
        """
        try:
            if frame is None:
                return

            if isinstance(frame, np.ndarray):
                self._last_frame = frame
                self._render_frame(frame)
                if getattr(self, "_semi_live", False):
                    self._solve_frame(frame, force=False)
                else:
                    # still update overlay geometry to keep centered
                    self._update_overlay()
                return

            # Some implementations emit dict {frame:..., ts:...}
            if isinstance(frame, dict) and "frame" in frame and isinstance(frame["frame"], np.ndarray):
                self._last_frame = frame["frame"]
                self._render_frame(frame["frame"])
                if getattr(self, "_semi_live", False):
                    self._solve_frame(frame["frame"], force=False)
                else:
                    self._update_overlay()
                return

        except Exception as e:
            self._set_status(f"Error procesando frame: {e}")

    def _render_frame(self, frame: np.ndarray):
        qimg = _qimage_from_ndarray(frame)
        if qimg.isNull():
            return

        pix = QPixmap.fromImage(qimg)
        self.frame_item.setPixmap(pix)

        w = pix.width()
        h = pix.height()

        # Scene rect = image rect
        self.scene.setSceneRect(QRectF(0, 0, w, h))

        # Fit view while preserving aspect
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

        # Update center (target)
        self.state.center = (w / 2.0, h / 2.0)
        self._set_overlay_visible(True)

        # Move the top hint
        self.top_hint.setPos(14, 10)

        self._update_overlay()

    # ─────────────────────────
    # Solver (simple Polaris tracking)
    # ─────────────────────────
    def _solve_frame(self, frame: np.ndarray, force: bool):
        """
        This is NOT a real plate-solve; it’s a stable Polaris tracker.
        - Finds brightest star
        - Stabilizes using previous position (seed search)
        - Computes error vector relative to center

        ADDED:
        - Polaris temporal confirmation (must be stable N frames)
        - Until confirmed: no arrows, orange point, status "Confirmando Polaris..."
        - After confirmed: arrows enabled, green point
        """
        now = time.time()
        if not force and (now - self.state.last_t) < 0.10:
            return  # throttle
        self.state.last_t = now

        # Determine seed (stabilize)
        seed = self.state.polaris_s if self.state.polaris_s is not None else self.state.polaris
        p = _centroid_brightest(frame, seed=seed, search_radius=140 if seed else 999999)

        if p is None:
            self._set_status("No se detecta Polaris (insuficientes estrellas / señal).")
            self.state.polaris = None
            self.state.polaris_s = None

            # ADDED: reset confirmation on lost polaris
            self.state.polaris_confirmed = False
            self.state.confirm_count = 0
            self.state.last_confirm_pos = None

            self._update_errors(0.0, 0.0)
            self._update_overlay()
            return

        self.state.polaris = p

        # Smooth
        if self.state.polaris_s is None:
            self.state.polaris_s = p
        else:
            a = 0.25  # smoothing factor
            self.state.polaris_s = (
                self.state.polaris_s[0] * (1 - a) + p[0] * a,
                self.state.polaris_s[1] * (1 - a) + p[1] * a,
            )

        # ────────────────────────────────
        # ADDED: Temporal confirmation of Polaris
        # ────────────────────────────────
        if self.state.polaris_s is not None:
            if self.state.last_confirm_pos is None:
                self.state.last_confirm_pos = self.state.polaris_s
                self.state.confirm_count = 1
                self.state.polaris_confirmed = False
            else:
                dpx = _dist(self.state.polaris_s, self.state.last_confirm_pos)

                if dpx <= POLARIS_CONFIRM_RADIUS_PX:
                    self.state.confirm_count += 1
                else:
                    self.state.confirm_count = 0
                    self.state.polaris_confirmed = False

                # update last for next comparison
                self.state.last_confirm_pos = self.state.polaris_s

            if self.state.confirm_count >= POLARIS_CONFIRM_FRAMES:
                self.state.polaris_confirmed = True
        else:
            self.state.polaris_confirmed = False
            self.state.confirm_count = 0
            self.state.last_confirm_pos = None

        # Error vector: target center - polaris
        cx, cy = self.state.center
        px, py = self.state.polaris_s
        dx = cx - px
        dy = cy - py

        # Convert to arcmin (rough)
        arcmin_x = (dx * self.state.arcsec_per_px) / 60.0
        arcmin_y = (dy * self.state.arcsec_per_px) / 60.0

        # Update overlay always (dot position)
        self._update_overlay()

        # info panel
        dist_px = _dist((cx, cy), (px, py))
        dist_arcmin = (dist_px * self.state.arcsec_per_px) / 60.0

        # ADDED: Live confirmation text
        conf_txt = "CONFIRMADA ✅" if self.state.polaris_confirmed else f"confirmando… ({self.state.confirm_count}/{POLARIS_CONFIRM_FRAMES})"

        self.lbl_info.setText(
            f"Live View: OK\n"
            f"Polaris: x={px:.1f}, y={py:.1f} ({conf_txt})\n"
            f"Distancia al objetivo: {dist_arcmin:.2f}′\n"
            f"Escala: {self.state.arcsec_per_px:.2f} arcsec/px\n"
        )

        # ────────────────────────────────
        # MODIFIED: Only compute/show arrows AFTER confirmation
        # ────────────────────────────────
        if not self.state.polaris_confirmed:
            # while confirming, freeze errors and hide arrows
            self._set_status("Confirmando Polaris… mantén la montura estable")
            self._update_errors(0.0, 0.0)
            self.az_arrow.setVisible(False)
            self.alt_arrow.setVisible(False)
            return

        # Normal behavior after confirmation
        self._update_errors(arcmin_x, arcmin_y)

        if dist_arcmin < 0.5:
            self._set_status("Alineación correcta ✅")
        else:
            self._set_status("Ajusta Altitud / Azimut siguiendo las flechas…")

    # ─────────────────────────
    # Overlay drawing
    # ─────────────────────────
    def _update_overlay(self):
        # Need a scene rect
        rect = self.scene.sceneRect()
        if rect.isNull():
            return

        cx, cy = self.state.center
        w = rect.width()
        h = rect.height()

        # Target circle radius: 18% of smaller dimension (NINA-ish)
        r = max(40.0, min(w, h) * 0.18)
        self.target_circle.setRect(QRectF(cx - r, cy - r, 2 * r, 2 * r))

        # Crosshair length
        L = max(80.0, min(w, h) * 0.22)
        self.cross_h.setLine(cx - L, cy, cx + L, cy)
        self.cross_v.setLine(cx, cy - L, cx, cy + L)

        # Polaris dot
        if self.state.polaris_s is not None:
            px, py = self.state.polaris_s
            dot_r = 6.0
            self.polaris_dot.setRect(QRectF(px - dot_r, py - dot_r, 2 * dot_r, 2 * dot_r))

            # ADDED: change dot color depending on confirmation
            if getattr(self.state, "polaris_confirmed", False):
                col = QColor("#3cff4e")  # green confirmed
            else:
                col = QColor("#ff9a3d")  # orange confirming

            self.polaris_dot.setPen(QPen(col, 2))
            self.polaris_dot.setBrush(QBrush(col))

            self.polaris_dot.setVisible(True)
        else:
            self.polaris_dot.setVisible(False)

        # Arrows (derived from current labels if possible)
        ax = getattr(self, "_last_arcmin_x", 0.0)
        ay = getattr(self, "_last_arcmin_y", 0.0)

        # Map arcmin -> pixels for arrows (visual only)
        scale_px = 25.0  # px per arcmin, for UI
        vx = _clamp(ax * scale_px, -120, 120)
        vy = _clamp(ay * scale_px, -120, 120)

        self.az_arrow.setLine(cx, cy + r + 18, cx - vx, cy + r + 18)
        self.alt_arrow.setLine(cx + r + 18, cy, cx + r + 18, cy - vy)

        # MODIFIED: hide arrows if NOT confirmed
        if not getattr(self.state, "polaris_confirmed", False):
            self.az_arrow.setVisible(False)
            self.alt_arrow.setVisible(False)
            return

        # Hide arrows if almost aligned
        total = math.hypot(ax, ay)
        show = total >= 0.25
        self.az_arrow.setVisible(show)
        self.alt_arrow.setVisible(show)

    # ─────────────────────────
    # Error panels
    # ─────────────────────────
    @staticmethod
    def _fmt_arcmin(v: float) -> str:
        sign = "-" if v < 0 else ""
        v = abs(v)
        deg = int(v // 60.0)
        rem_min = v - deg * 60.0
        minute = int(rem_min)
        sec = int((rem_min - minute) * 60.0)
        return f"{sign}{deg:02d}° {minute:02d}′ {sec:02d}″"

    def _update_errors(self, arcmin_x: float, arcmin_y: float):
        self._last_arcmin_x = float(arcmin_x)
        self._last_arcmin_y = float(arcmin_y)

        total = math.hypot(arcmin_x, arcmin_y)

        az_dir = "Move left/west ←" if arcmin_x > 0 else ("Move right/east →" if arcmin_x < 0 else "—")
        alt_dir = "Move up ↑" if arcmin_y > 0 else ("Move down ↓" if arcmin_y < 0 else "—")

        self.az_box["big"].setText(self._fmt_arcmin(arcmin_x))
        self.az_box["hint"].setText(az_dir)
        self.az_box["small"].setText(f"{abs(arcmin_x):.2f}′")

        self.alt_box["big"].setText(self._fmt_arcmin(arcmin_y))
        self.alt_box["hint"].setText(alt_dir)
        self.alt_box["small"].setText(f"{abs(arcmin_y):.2f}′")

        self.total_box["big"].setText(self._fmt_arcmin(total))
        self.total_box["hint"].setText("—" if total < 0.25 else "Total Error")
        self.total_box["small"].setText(f"{total:.2f}′")

    # ─────────────────────────
    # Timers
    # ─────────────────────────
    def _tick_ui(self):
        self._update_overlay()
        if self._last_frame is None and not self.demo_timer.isActive():
            self.lbl_info.setText("Live View: —\nPolaris: —\n")

    # ─────────────────────────
    # Demo frames (Polaris-like)
    # ─────────────────────────
    def _demo_step(self):
        w, h = 1280, 720
        img = np.random.normal(10, 6, (h, w)).astype(np.float32)
        img = np.clip(img, 0, 255)

        cx, cy = w / 2, h / 2
        t = time.time()
        px = cx - 80 + math.sin(t * 0.8) * 2.0
        py = cy + 25 + math.cos(t * 0.7) * 2.0

        for _ in range(180):
            sx = np.random.randint(0, w)
            sy = np.random.randint(0, h)
            img[sy, sx] = 255

        rr = 7
        x0 = int(_clamp(px - rr, 0, w - 1))
        x1 = int(_clamp(px + rr, 0, w - 1))
        y0 = int(_clamp(py - rr, 0, h - 1))
        y1 = int(_clamp(py + rr, 0, h - 1))
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                d2 = (xx - px) ** 2 + (yy - py) ** 2
                img[yy, xx] += 220 * math.exp(-d2 / (2 * 2.2 ** 2))

        img = np.clip(img, 0, 255).astype(np.uint8)

        self._last_frame = img
        self._render_frame(img)

        if getattr(self, "_semi_live", True):
            self._semi_live = True
            self.btn_semi_live.setText("⏸ Pausar semi-en vivo")
            self._solve_frame(img, force=False)
        else:
            self._update_overlay()
