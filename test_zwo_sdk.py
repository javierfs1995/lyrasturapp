import ctypes
import os

# Rutas típicas donde ZWO instala el SDK
possible_paths = [
    r"C:\Program Files\ZWO Design\ASI SDK\include\lib\x64\ASICamera2.dll",
    r"C:\Program Files (x86)\ZWO Design\ASI SDK\include\lib\x64\ASICamera2.dll",
]

dll = None
for path in possible_paths:
    if os.path.exists(path):
        print(f"SDK encontrado en: {path}")
        dll = ctypes.WinDLL(path)
        break

if dll is None:
    raise RuntimeError("No se encontró ASICamera2.dll")

# Función básica del SDK
dll.ASIGetNumOfConnectedCameras.restype = ctypes.c_int

num = dll.ASIGetNumOfConnectedCameras()
print("Cámaras conectadas:", num)
