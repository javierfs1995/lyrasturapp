import cv2

from solver.frame_loader import load_frame
from solver.star_detection import detect_stars
from solver.rotation_solver import compute_rotation_center

# CAMBIA LA EXTENSIÓN SI ES NECESARIO
A_PATH = "solver/data/polaris/frame_a.png"
B_PATH = "solver/data/polaris/frame_b.png"

# Cargar imágenes reales
frame_a = load_frame(A_PATH)
frame_b = load_frame(B_PATH)

# Detectar estrellas
stars_a = detect_stars(frame_a)
stars_b = detect_stars(frame_b)

print(f"Estrellas A: {len(stars_a)}")
print(f"Estrellas B: {len(stars_b)}")

# Centro de rotación
center = compute_rotation_center(stars_a, stars_b)
print("Centro de rotación (px):", center)

# Visualización
vis = cv2.cvtColor(frame_a, cv2.COLOR_GRAY2BGR)

for x, y in stars_a:
    cv2.circle(vis, (int(x), int(y)), 1, (255, 255, 255), -1)

cv2.circle(vis, (int(center[0]), int(center[1])), 10, (0, 255, 0), 2)

cv2.imshow("Polar Alignment – Datos reales", vis)
cv2.waitKey(0)
cv2.destroyAllWindows()
