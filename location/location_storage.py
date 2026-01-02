import json
from pathlib import Path


LOCATION_FILE = Path("config/location.json")


def load_location():
    if not LOCATION_FILE.exists():
        return None

    with open(LOCATION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_location(city: str, lat: float, lon: float):
    LOCATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "city": city,
        "lat": lat,
        "lon": lon
    }
    with open(LOCATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
