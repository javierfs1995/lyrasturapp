import cv2
import numpy as np

from solver.sky_simulator import generate_synthetic_sky, rotate_frame
from solver.star_detection import detect_stars
from solver.rotation_solver import compute_rotation_center

# Generar frame A
frame_a = generate_synthetic_sky()
stars_a = detect_stars(frame_a)

# Rotar alrededor de un centro artificial desplazado
h, w = frame_a.shape
true_center = (w / 2 + 30, h / 2 - 20)

frame_b = rotate_frame(frame_a, angle_deg=15, center=true_center)
stars_b = detect_stars(frame_b)

# Calcular centro de rotación
calc_center = compute_rotation_center(stars_a, stars_b)

print("Centro real:", true_center)
print("Centro calculado:", calc_center)

# Visualizar
vis = cv2.cvtColor(frame_a, cv2.COLOR_GRAY2BGR)

cv2.circle(vis, (int(true_center[0]), int(true_center[1])), 6, (255, 0, 0), 2)
cv2.circle(vis, (int(calc_center[0]), int(calc_center[1])), 6, (0, 255, 0), 2)

cv2.imshow("Rotation Center (Blue=Real, Green=Calculated)", vis)
cv2.waitKey(0)
cv2.destroyAllWindows()
