# ui/sequence_page.py
# SequencePage + SequenceWorker (MODELO A estilo FireCapture)
# - STOP LiveViewService antes de capturar
# - Captura en QThread (no bloquea UI)
# - Restaura LiveViewService al terminar
# - Guarda AVI (MJPG) y FITS (si astropy está instalado)

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any

import numpy as np
import cv2

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGroupBox, QGridLayout,
    QSpinBox, QDoubleSpinBox, QSplitter,
    QFileDialog, QMessageBox, QComboBox, QSlider
)

from ui.live_view_panel import LiveViewPanel


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _safe_call(obj, name: str, *args, **kwargs):
    fn = getattr(obj, name, None)
    if callable(fn):
        return fn(*args, **kwargs)
    return None


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _to_bgr(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.ndim == 3 and frame.shape[2] == 3:
        return frame
    if frame.ndim == 3 and frame.shape[2] == 4:
        return frame[:, :, :3]
    g = frame.astype(np.uint8)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)


def save_avi_mjpg(frames: List[np.ndarray], path: str, fps: float):
    if not frames:
        raise RuntimeError("No se capturaron frames (lista vacía).")

    fps = float(max(1.0, fps))
    h, w = frames[0].shape[:2]

    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(path, fourcc, fps, (w, h), True)
    if not writer.isOpened():
        raise RuntimeError("No se pudo abrir el writer AVI (MJPG).")

    try:
        for f in frames:
            writer.write(_to_bgr(f))
    finally:
        writer.release()


def save_fits(frame: np.ndarray, path: str):
    try:
        from astropy.io import fits  # type: ignore
    except Exception:
        raise RuntimeError("Para guardar FITS necesitas: pip install astropy")

    data = frame
    if data.ndim == 3:
        data = data[:, :, 0]

    hdu = fits.PrimaryHDU(data.astype(np.uint16) if data.dtype != np.uint16 else data)
    hdul = fits.HDUList([hdu])
    hdul.writeto(path, overwrite=True)


# ─────────────────────────────────────────────
# Config de secuencia
# ─────────────────────────────────────────────
@dataclass
class SequenceConfig:
    cap_type: str
    exposure_s: float
    gain: int
    n_caps: int
    duration_s: Optional[float]
    roi: Optional[tuple[int, int, int, int]]
    out_dir: str
    fps: float
    base_name: str


# ─────────────────────────────────────────────
# Worker (en QThread) — MODELO A
# ─────────────────────────────────────────────
class SequenceWorker(QObject):
    progress = Signal(str)
    finished = Signal(list)  # rutas generadas
    error = Signal(str)

    def __init__(self, cam, cfg: SequenceConfig):
        super().__init__()
        self.cam = cam
        self.cfg = cfg
        self._abort = False
        self._saved_state: Dict[str, Any] = {}

    def request_abort(self):
        self._abort = True

    def run(self):
        try:
            self.progress.emit("Preparando cámara…")
            self._save_camera_state()
            self._apply_capture_state()

            outputs: List[str] = []

            for i in range(1, self.cfg.n_caps + 1):
                if self._abort:
                    self.progress.emit("Secuencia detenida por el usuario.")
                    break

                if self.cfg.cap_type == "FITS":
                    self.progress.emit(f"Capturando FITS {i}/{self.cfg.n_caps}…")
                    frame = self._capture_single_frame()
                    out = os.path.join(self.cfg.out_dir, f"{self.cfg.base_name}_{_timestamp()}_{i:03d}.fits")
                    save_fits(frame, out)
                    outputs.append(out)

                elif self.cfg.cap_type == "AVI":
                    dur = float(self.cfg.duration_s or 0.0)
                    if dur <= 0:
                        raise RuntimeError("Duración inválida para AVI.")
                    self.progress.emit(f"Grabando AVI {i}/{self.cfg.n_caps} ({dur:.1f}s)…")
                    frames, fps_real = self._capture_video(dur, self.cfg.fps)
                    out = os.path.join(self.cfg.out_dir, f"{self.cfg.base_name}_{_timestamp()}_{i:03d}.avi")
                    save_avi_mjpg(frames, out, fps_real)
                    outputs.append(out)

                elif self.cfg.cap_type == "SER":
                    raise RuntimeError("SER aún no implementado (TODO).")

                else:
                    raise RuntimeError(f"Tipo no soportado: {self.cfg.cap_type}")

            self.progress.emit("Restaurando cámara…")
            self._restore_camera_state()

            self.finished.emit(outputs)

        except Exception as e:
            try:
                self._restore_camera_state()
            except Exception:
                pass
            self.error.emit(str(e))

    def _save_camera_state(self):
        self._saved_state["exposure_ms"] = None
        self._saved_state["gain"] = None
        self._saved_state["roi"] = None

    def _apply_capture_state(self):
        if self.cfg.roi is not None:
            x, y, w, h = self.cfg.roi
            _safe_call(self.cam, "set_roi", int(x), int(y), int(w), int(h))

        _safe_call(self.cam, "set_gain", int(self.cfg.gain))
        _safe_call(self.cam, "set_exposure", float(self.cfg.exposure_s * 1000.0))

        _safe_call(self.cam, "start_live")

        for _ in range(2):
            if self._abort:
                return
            _ = self._get_frame_safe()
            time.sleep(0.02)

    def _restore_camera_state(self):
        _safe_call(self.cam, "stop_live")
        _safe_call(self.cam, "set_roi", 0, 0, 999999, 999999)

    def _get_frame_safe(self) -> np.ndarray:
        frame = _safe_call(self.cam, "get_frame")
        if frame is None:
            raise RuntimeError("La cámara devolvió frame=None (get_frame).")
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            raise RuntimeError("Frame inválido devuelto por la cámara.")
        return frame

    def _capture_single_frame(self) -> np.ndarray:
        if callable(getattr(self.cam, "capture", None)):
            frame = self.cam.capture(float(self.cfg.exposure_s * 1000.0))
            if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                raise RuntimeError("capture() devolvió frame inválido.")
            return frame

        time.sleep(float(self.cfg.exposure_s))
        return self._get_frame_safe()

    def _capture_video(self, duration_s: float, target_fps: float) -> tuple[List[np.ndarray], float]:
        duration_s = float(max(0.05, duration_s))
        target_fps = float(max(1.0, target_fps))
        dt = 1.0 / target_fps

        frames: List[np.ndarray] = []
        t0 = time.time()
        t_next = t0

        while not self._abort and (time.time() - t0) < duration_s:
            now = time.time()
            if now < t_next:
                time.sleep(min(0.01, t_next - now))
                continue

            f = self._get_frame_safe()
            frames.append(f.copy())
            t_next += dt

        elapsed = max(1e-6, time.time() - t0)
        fps_real = len(frames) / elapsed if frames else target_fps

        if not frames:
            raise RuntimeError("No se capturaron frames durante la grabación.")

        return frames, fps_real


# ─────────────────────────────────────────────
# UI Page
# ─────────────────────────────────────────────
class SequencePage(QWidget):
    def __init__(self, cam_manager, live_service, parent=None):
        super().__init__(parent)

        self.cam = cam_manager
        self.live = live_service

        self.output_dir: Optional[str] = None
        self.roi: Optional[tuple[int, int, int, int]] = None

        self._thread: Optional[QThread] = None
        self._worker: Optional[SequenceWorker] = None

        self._build_ui()
        self._wire_live()
        self._wire_ui()

        # defaults preview
        self.live_panel.live_view.set_zoom("MAX")
        self.live_panel.live_view.set_color(True)
        self.live_panel.live_view.set_bayer_pattern("BGGR")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("🧪 Sequence")
        title.setStyleSheet("font-size:16px; font-weight:800;")
        header.addWidget(title)
        header.addStretch()

        self.lbl_status = QLabel("—")
        self.lbl_status.setStyleSheet("color:#8b95a3;")
        header.addWidget(self.lbl_status)

        root.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        self.left = self._card()
        self.left.setFixedWidth(340)
        l = QVBoxLayout(self.left)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(12)

        gb = QGroupBox("Secuencia")
        gb.setStyleSheet("""
            QGroupBox {
                font-weight: 700;
                border: 1px solid white;
                border-radius: 8px;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                color: #cfd6dd;
            }
        """)
        gl = QGridLayout(gb)


        gl.setColumnMinimumWidth(0, 140)   # columna de labels
        gl.setColumnStretch(0, 0)
        gl.setColumnStretch(1, 1)          # columna de controles
        gl.setHorizontalSpacing(12)
        gl.setVerticalSpacing(8)

        gl.addWidget(QLabel("Tipo"), 0, 0)
        self.cb_type = QComboBox()
        self.cb_type.addItems(["AVI", "FITS", "SER"])
        gl.addWidget(self.cb_type, 0, 1)

        lbl = QLabel("Exposición (s)")
        lbl.setMinimumWidth(130)
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        gl.addWidget(lbl, 1, 0)

        self.sp_exp = QDoubleSpinBox()
        self.sp_exp.setRange(0.001, 3600.0)
        self.sp_exp.setDecimals(3)
        self.sp_exp.setValue(0.020)
        gl.addWidget(self.sp_exp, 1, 1)

        gl.addWidget(QLabel("Ganancia"), 2, 0)
        self.sp_gain = QSpinBox()
        self.sp_gain.setRange(0, 500)
        self.sp_gain.setValue(120)
        gl.addWidget(self.sp_gain, 2, 1)

        gl.addWidget(QLabel("Nº capturas"), 3, 0)
        self.sp_captures = QSpinBox()
        self.sp_captures.setRange(1, 10000)
        self.sp_captures.setValue(3)
        gl.addWidget(self.sp_captures, 3, 1)

        gl.addWidget(QLabel("Duración vídeo (s)"), 4, 0)
        self.sp_duration = QDoubleSpinBox()
        self.sp_duration.setRange(0.1, 36000.0)
        self.sp_duration.setDecimals(1)
        self.sp_duration.setValue(10.0)
        gl.addWidget(self.sp_duration, 4, 1)

        gl.addWidget(QLabel("FPS (AVI)"), 5, 0)
        self.sp_fps = QDoubleSpinBox()
        self.sp_fps.setRange(1.0, 120.0)
        self.sp_fps.setDecimals(1)
        self.sp_fps.setValue(30.0)
        gl.addWidget(self.sp_fps, 5, 1)

        l.addWidget(gb)

        # ───── White Balance (preview)
        gb_wb = QGroupBox("Balance Blancos (preview)")
        gb_wb.setStyleSheet("""
            QGroupBox {
                font-weight: 700;
                border: 1px solid white;
                border-radius: 8px;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                color: #cfd6dd;
            }
        """)
        gw = QGridLayout(gb_wb)

        gw.setColumnMinimumWidth(0, 22)
        gw.setColumnStretch(1, 1)
        gw.setHorizontalSpacing(10)
        gw.setVerticalSpacing(6)

        self.sl_wb_r = QSlider(Qt.Horizontal)
        self.sl_wb_r.setRange(50, 250)
        self.sl_wb_r.setValue(100)

        self.sl_wb_g = QSlider(Qt.Horizontal)
        self.sl_wb_g.setRange(50, 250)
        self.sl_wb_g.setValue(100)

        self.sl_wb_b = QSlider(Qt.Horizontal)
        self.sl_wb_b.setRange(50, 250)
        self.sl_wb_b.setValue(100)

        for sl in (self.sl_wb_r, self.sl_wb_g, self.sl_wb_b):
            sl.setMinimumHeight(18)
            from PySide6.QtWidgets import QSizePolicy
            sl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        gw.addWidget(QLabel("R"), 0, 0); gw.addWidget(self.sl_wb_r, 0, 1)
        gw.addWidget(QLabel("G"), 1, 0); gw.addWidget(self.sl_wb_g, 1, 1)
        gw.addWidget(QLabel("B"), 2, 0); gw.addWidget(self.sl_wb_b, 2, 1)

        l.addWidget(gb_wb)
        
        self.btn_auto_wb = QPushButton("Auto WB (ROI)")
        l.addWidget(self.btn_auto_wb)

        # Destino
        gb_out = QGroupBox("Destino")
        gb_out.setStyleSheet("""
            QGroupBox {
                font-weight: 700;
                border: 1px solid white;
                border-radius: 8px;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                color: #cfd6dd;
            }
        """)
        gl_out = QGridLayout(gb_out)

        gl_out.setColumnStretch(0, 1)
        gl_out.setHorizontalSpacing(8)
        gl_out.setVerticalSpacing(6)

        self.lbl_out_dir = QLabel("No seleccionado")
        self.lbl_out_dir.setWordWrap(True)
        self.lbl_out_dir.setStyleSheet("color:#8b95a3;")
        self.btn_browse = QPushButton("📂 Elegir carpeta")

        gl_out.addWidget(self.lbl_out_dir, 0, 0, 1, 2)
        gl_out.addWidget(self.btn_browse, 1, 0, 1, 2)

        l.addWidget(gb_out)

        # Start/Stop
        self.btn_start = QPushButton("▶ Iniciar secuencia")
        self.btn_stop = QPushButton("■ Detener")
        self.btn_stop.setEnabled(False)

        l.addWidget(self.btn_start)
        l.addWidget(self.btn_stop)
        l.addStretch(1)

        # Center: Live view panel
        self.live_panel = LiveViewPanel()

        splitter.addWidget(self.left)
        splitter.addWidget(self.live_panel)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)

        self._on_type_changed(self.cb_type.currentText())

        for lbl in self.findChildren(QLabel):
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def _card(self) -> QFrame:
        w = QFrame()
        w.setStyleSheet("background:#171a20; border:1px solid #23262d; border-radius:12px;")
        return w

    def _wire_live(self):
        # Solo preview: frames → panel
        self.live.frame_ready.connect(self.live_panel.live_view.set_frame)
        self.live.frame_ready.connect(self.live_panel.histogram.set_frame)

    def _wire_ui(self):
        self.btn_browse.clicked.connect(self.choose_output_dir)
        self.btn_start.clicked.connect(self.start_sequence)
        self.btn_stop.clicked.connect(self.stop_sequence)

        self.cb_type.currentTextChanged.connect(self._on_type_changed)

        # WB SOLO aquí (no en _wire_live)
        self.sl_wb_r.valueChanged.connect(self._on_wb_changed)
        self.sl_wb_g.valueChanged.connect(self._on_wb_changed)
        self.sl_wb_b.valueChanged.connect(self._on_wb_changed)
        self.btn_auto_wb.clicked.connect(
            self.live_panel.live_view.auto_white_balance_roi
        )

    def _on_type_changed(self, text: str):
        is_video = text in ("AVI", "SER")
        self.sp_duration.setEnabled(is_video)
        self.sp_duration.setVisible(is_video)

        self.sp_fps.setEnabled(text == "AVI")
        self.sp_fps.setVisible(text == "AVI")

    def _on_wb_changed(self):
        r = self.sl_wb_r.value() / 100.0
        g = self.sl_wb_g.value() / 100.0
        b = self.sl_wb_b.value() / 100.0
        self.live_panel.live_view.set_white_balance(r, g, b)

    def choose_output_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Elegir carpeta de destino", self.output_dir or os.getcwd()
        )
        if not path:
            return
        self.output_dir = path
        self.lbl_out_dir.setText(path)

    def start_sequence(self):
        if self._thread is not None:
            return

        if not self.output_dir:
            QMessageBox.warning(self, "Destino no definido", "Selecciona una carpeta de destino.")
            return

        cap_type = self.cb_type.currentText().strip()
        if cap_type == "SER":
            QMessageBox.information(self, "SER", "SER está marcado como TODO. Usa AVI o FITS por ahora.")
            return

        cfg = SequenceConfig(
            cap_type=cap_type,
            exposure_s=float(self.sp_exp.value()),
            gain=int(self.sp_gain.value()),
            n_caps=int(self.sp_captures.value()),
            duration_s=float(self.sp_duration.value()) if cap_type in ("AVI", "SER") else None,
            roi=self.roi,
            out_dir=self.output_dir,
            fps=float(self.sp_fps.value()),
            base_name="sequence",
        )
        _ensure_dir(cfg.out_dir)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("Deteniendo Live View…")

        try:
            self.live.stop()
        except Exception:
            pass

        self._thread = QThread(self)
        self._worker = SequenceWorker(self.cam, cfg)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._thread.start()

    def stop_sequence(self):
        if self._worker is not None:
            self._worker.request_abort()
            self.lbl_status.setText("Deteniendo secuencia…")
        self.btn_stop.setEnabled(False)

    def _on_progress(self, msg: str):
        self.lbl_status.setText(msg)

    def _cleanup_thread(self):
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None

    def _restart_live(self):
        try:
            self.live.start(12)
        except Exception:
            pass

    def _on_finished(self, outputs: list):
        self._cleanup_thread()
        self._restart_live()

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        if not outputs:
            self.lbl_status.setText("Secuencia finalizada (sin archivos).")
            QMessageBox.information(self, "Secuencia", "Secuencia finalizada, pero no se generaron archivos.")
            return

        self.lbl_status.setText("Secuencia finalizada ✅")
        QMessageBox.information(
            self,
            "Secuencia finalizada",
            "Archivos generados:\n\n" + "\n".join(outputs[:10]) + ("" if len(outputs) <= 10 else "\n…")
        )

    def _on_error(self, msg: str):
        self._cleanup_thread()
        self._restart_live()

        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        self.lbl_status.setText("Error ❌")
        QMessageBox.critical(self, "Error en secuencia", msg)
