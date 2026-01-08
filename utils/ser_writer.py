from __future__ import annotations

import struct
import time
import numpy as np

# ─────────────────────────────────────────────
# SER Color IDs (estándar)
# ─────────────────────────────────────────────
SER_COLOR_MONO = 0
SER_COLOR_BAYER_RGGB = 8
SER_COLOR_BAYER_BGGR = 9
SER_COLOR_BAYER_GRBG = 10
SER_COLOR_BAYER_GBRG = 11


class SERWriter:
    """
    Escritor SER compatible con:
      - FireCapture
      - AutoStakkert
      - PIPP
      - SER Player

    Soporta:
      - Mono
      - Color Bayer (RAW, sin debayerizar)
    """

    def __init__(
        self,
        path: str,
        width: int,
        height: int,
        *,
        color: bool = False,
        bayer_pattern: str | None = None,
        bit_depth: int = 8,
        fps: float = 30.0,
        observer: str = "astroapp",
        instrument: str = "Camera",
        telescope: str = "Telescope",
    ):
        self.path = path
        self.width = width
        self.height = height
        self.color = color
        self.bayer_pattern = bayer_pattern
        self.bit_depth = bit_depth
        self.fps = fps

        self.frame_count = 0
        self.timestamps: list[int] = []

        self._file = open(path, "wb")

        self._write_header(observer, instrument, telescope)

    # ─────────────────────────────────────────────
    # Header SER
    # ─────────────────────────────────────────────

    def _write_header(self, observer: str, instrument: str, telescope: str):
        """
        Header SER estándar (178 bytes)
        """

        endian = 0  # little endian

        if not self.color:
            color_id = SER_COLOR_MONO
        else:
            bayer_map = {
                "RGGB": SER_COLOR_BAYER_RGGB,
                "BGGR": SER_COLOR_BAYER_BGGR,
                "GRBG": SER_COLOR_BAYER_GRBG,
                "GBRG": SER_COLOR_BAYER_GBRG,
            }
            color_id = bayer_map.get(self.bayer_pattern, SER_COLOR_MONO)

        header = struct.pack(
            "<14sIIIIIIII40s40s40sQ",
            b"LUCAM-RECORDER",      # File ID
            0,                     # LuID
            color_id,              # ColorID
            endian,                # Endianess
            self.width,            # Image width
            self.height,           # Image height
            self.bit_depth,        # Pixel depth
            int(self.fps * 1000),  # Frame rate (milli-FPS)
            0,                     # Frame count (se parchea al cerrar)
            0,                     # Observer ID
            observer.encode("ascii", "ignore").ljust(40, b"\0"),
            instrument.encode("ascii", "ignore").ljust(40, b"\0"),
            telescope.encode("ascii", "ignore").ljust(40, b"\0"),
            0,                     # DateTime (no usado)
        )

        self._file.write(header)

    # ─────────────────────────────────────────────
    # Escribir frame
    # ─────────────────────────────────────────────

    def write(self, frame: np.ndarray):
        """
        Escribe un frame crudo.
        ⚠️ NO debayeriza (estilo FireCapture)
        """

        if frame is None:
            return

        if frame.dtype != np.uint8:
            frame = np.clip(frame, 0, 255).astype(np.uint8)

        # Si llega RGB por error, cogemos un canal (fallback seguro)
        if frame.ndim == 3:
            frame = frame[..., 0]

        self._file.write(frame.tobytes())

        # Timestamp SER (microsegundos desde epoch)
        ts = int(time.time() * 1_000_000)
        self.timestamps.append(ts)

        self.frame_count += 1

    # ─────────────────────────────────────────────
    # Cerrar SER
    # ─────────────────────────────────────────────

    def close(self):
        """
        Escribe timestamps y parchea el número de frames
        """

        # Timestamps al final
        for ts in self.timestamps:
            self._file.write(struct.pack("<Q", ts))

        # Parchear número de imágenes
        self._file.seek(38)
        self._file.write(struct.pack("<I", self.frame_count))

        self._file.close()
