import cv2
from solver.sky_simulator import generate_synthetic_sky, rotate_frame
from solver.star_detection import detect_stars

# Frame A
frame_a = generate_synthetic_sky()
stars_a = detect_stars(frame_a)

# Frame B (simula giro RA)
frame_b = rotate_frame(frame_a, angle_deg=15)
stars_b = detect_stars(frame_b)

print(f"Estrellas A: {len(stars_a)}")
print(f"Estrellas B: {len(stars_b)}")

# Visualizar estrellas detectadas
vis = cv2.cvtColor(frame_a, cv2.COLOR_GRAY2BGR)
for x, y in stars_a:
    cv2.circle(vis, (int(x), int(y)), 2, (0, 255, 0), -1)

cv2.imshow("Synthetic Sky - Stars Detected", vis)
cv2.waitKey(0)
cv2.destroyAllWindows()
