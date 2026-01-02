import cv2

from solver.frame_loader import load_frame
from solver.star_detection import detect_stars
from solver.rotation_solver import compute_rotation_center
from solver.polar_error import compute_polar_error_arcmin

# Ajusta extensión si es necesario
A_PATH = "solver/data/polaris/frame_a.png"
B_PATH = "solver/data/polaris/frame_b.png"

FOCAL_MM = 700.0
PIXEL_SIZE_UM = 2.0

frame_a = load_frame(A_PATH)
frame_b = load_frame(B_PATH)

stars_a = detect_stars(frame_a)
stars_b = detect_stars(frame_b)

center = compute_rotation_center(stars_a, stars_b)

h, w = frame_a.shape
sensor_center = (w / 2, h / 2)

error_az, error_alt = compute_polar_error_arcmin(
    center,
    sensor_center,
    FOCAL_MM,
    PIXEL_SIZE_UM
)

print("Centro de rotación (px):", center)
print("Error AZ (arcmin):", round(error_az, 2))
print("Error ALT (arcmin):", round(error_alt, 2))

# Visual
vis = cv2.cvtColor(frame_a, cv2.COLOR_GRAY2BGR)
cv2.circle(vis, (int(center[0]), int(center[1])), 8, (0, 255, 0), 2)
cv2.circle(vis, (int(sensor_center[0]), int(sensor_center[1])), 6, (255, 0, 0), 2)

cv2.imshow("Polar Error (Green=Axis, Blue=Sensor)", vis)
cv2.waitKey(0)
cv2.destroyAllWindows()
