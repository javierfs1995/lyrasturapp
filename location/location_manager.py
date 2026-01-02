import requests
from dataclasses import dataclass
from location.location_storage import load_location


@dataclass
class Location:
    city: str
    lat: float
    lon: float


def get_current_location() -> Location:
    stored = load_location()
    if stored:
        return Location(
            city=stored.get("city", "Ubicación guardada"),
            lat=float(stored["lat"]),
            lon=float(stored["lon"]),
        )

    # Fallback por IP
    try:
        r = requests.get("https://ipinfo.io/json", timeout=5)
        data = r.json()
        lat, lon = data.get("loc", "0,0").split(",")

        return Location(
            city=data.get("city", "Ubicación aproximada"),
            lat=float(lat),
            lon=float(lon),
        )
    except Exception:
        return Location(city="Oviedo", lat=43.3619, lon=-5.8494)
