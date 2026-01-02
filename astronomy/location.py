import json
import os
import geocoder
import requests

CONFIG_PATH = "config/location.json"


def load_location():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_location(data):
    os.makedirs("config", exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def detect_location_by_ip():
    g = geocoder.ip("me")
    if not g.ok:
        return None

    lat, lon = g.latlng
    place = reverse_geocode(lat, lon)

    return {
        "name": place.get("name", "Auto (IP)"),
        "city": place.get("city", ""),
        "region": place.get("region", ""),
        "country": place.get("country", ""),
        "lat": lat,
        "lon": lon,
        "elevation": 0
    }


def reverse_geocode(lat, lon):
    """
    Devuelve un nombre humano (city/town/village + región + país) para una coordenada.
    """
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json"},
            headers={"User-Agent": "AstroApp"},
            timeout=10
        ).json()

        address = r.get("address", {})
        city = address.get("city") or address.get("town") or address.get("village") or address.get("hamlet") or ""
        region = address.get("state") or address.get("region") or address.get("province") or ""
        country = (address.get("country_code") or "").upper()

        # Un nombre “bonito”
        parts = [p for p in [city, region, country] if p]
        name = ", ".join(parts) if parts else "Ubicación"

        return {"name": name, "city": city, "region": region, "country": country}
    except Exception:
        return {"name": "Ubicación", "city": "", "region": "", "country": ""}


def get_elevation(lat, lon):
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/elevation",
            params={"latitude": lat, "longitude": lon},
            timeout=10
        ).json()
        return int(r["elevation"][0])
    except Exception:
        return 0
