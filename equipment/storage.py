from __future__ import annotations
import json
from pathlib import Path
from typing import Dict

from equipment.profiles import EquipmentProfile, Telescope, Camera


class JsonProfileStorage:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load_profiles(self) -> Dict[str, EquipmentProfile]:
        if not self.path.exists():
            return {}

        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        profiles: Dict[str, EquipmentProfile] = {}

        for p in raw.get("profiles", []):
            prof = EquipmentProfile(
                name=p["name"],
                telescope=Telescope(
                    name=p["telescope"]["name"],
                    focal_mm=float(p["telescope"]["focal_mm"])
                ),
                camera=Camera(
                    name=p["camera"]["name"],
                    pixel_um=float(p["camera"]["pixel_um"])
                ),
                focal_multiplier=float(p.get("focal_multiplier", 1.0))
            )
            profiles[prof.name] = prof

        return profiles

    def save_profiles(self, profiles: Dict[str, EquipmentProfile]) -> None:
        data = {
            "profiles": []
        }

        for p in profiles.values():
            data["profiles"].append({
                "name": p.name,
                "telescope": {
                    "name": p.telescope.name,
                    "focal_mm": p.telescope.focal_mm
                },
                "camera": {
                    "name": p.camera.name,
                    "pixel_um": p.camera.pixel_um
                },
                "focal_multiplier": p.focal_multiplier
            })

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
