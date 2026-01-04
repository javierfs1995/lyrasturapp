import os
import math
import numpy as np
import cv2

def _add_star(img, x, y, peak=255, sigma=1.2):
    h, w = img.shape
    r = int(max(3, sigma * 4))
    x0, x1 = max(0, x - r), min(w, x + r + 1)
    y0, y1 = max(0, y - r), min(h, y + r + 1)

    xs = np.arange(x0, x1) - x
    ys = np.arange(y0, y1) - y
    xx, yy = np.meshgrid(xs, ys)
    g = np.exp(-(xx*xx + yy*yy) / (2 * sigma * sigma))
    patch = (peak * g).astype(np.float32)

    img[y0:y1, x0:x1] = np.clip(img[y0:y1, x0:x1].astype(np.float32) + patch, 0, 255).astype(np.uint8)

def _make_starfield(w=1280, h=720, n_stars=450, seed=123):
    rng = np.random.default_rng(seed)

    # fondo con ruido fino + viñeteo suave
    base = rng.normal(loc=10, scale=4, size=(h, w)).astype(np.float32)
    base = np.clip(base, 0, 255)

    # viñeteo
    y = np.linspace(-1, 1, h)[:, None]
    x = np.linspace(-1, 1, w)[None, :]
    vign = 1.0 - 0.25 * (x*x + y*y)
    vign = np.clip(vign, 0.6, 1.0)
    base *= vign

    img = np.clip(base, 0, 255).astype(np.uint8)

    # estrellas
    for _ in range(n_stars):
        sx = int(rng.integers(0, w))
        sy = int(rng.integers(0, h))
        mag = rng.uniform(0.2, 1.0)  # “brillo”
        peak = int(40 + 160 * (mag ** 2.2))
        sigma = float(rng.uniform(0.8, 1.8))
        _add_star(img, sx, sy, peak=peak, sigma=sigma)

    # “Polaris” (más brillante + un poco más gorda)
    pol_x = int(w * 0.52)
    pol_y = int(h * 0.48)
    _add_star(img, pol_x, pol_y, peak=255, sigma=2.4)
    _add_star(img, pol_x + 2, pol_y - 1, peak=160, sigma=1.6)  # halo/compañía fake

    # blur mínimo para parecer sensor real
    img = cv2.GaussianBlur(img, (0, 0), 0.6)

    return img

def _transform(img, rot_deg=0.0, shift_xy=(0, 0)):
    h, w = img.shape
    cx, cy = w / 2, h / 2
    M = cv2.getRotationMatrix2D((cx, cy), rot_deg, 1.0)
    M[0, 2] += shift_xy[0]
    M[1, 2] += shift_xy[1]
    out = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return out

def generate_demo(out_dir="demo_frames", w=1280, h=720):
    os.makedirs(out_dir, exist_ok=True)

    # Frame base (Captura 1)
    img1 = _make_starfield(w=w, h=h, n_stars=520, seed=2026)

    # Captura 2: simulamos giro RA ~ 60º + pequeño “error polar” -> shift sutil
    # (esto es justo lo que tu solver debe detectar)
    img2 = _transform(img1, rot_deg=58.0, shift_xy=(7, -5))

    # ruido distinto en el segundo frame
    rng = np.random.default_rng(999)
    noise = rng.normal(0, 2.5, size=img2.shape).astype(np.float32)
    img2 = np.clip(img2.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    p1 = os.path.join(out_dir, "capture1.png")
    p2 = os.path.join(out_dir, "capture2.png")
    cv2.imwrite(p1, img1)
    cv2.imwrite(p2, img2)
    return p1, p2

if __name__ == "__main__":
    p1, p2 = generate_demo()
    print("OK. Generadas:")
    print(" -", p1)
    print(" -", p2)
