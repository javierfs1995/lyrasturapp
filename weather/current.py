import requests

def get_current_weather(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,cloud_cover,wind_speed_10m,relative_humidity_2m"
        "&timezone=auto"
    )
    data = requests.get(url, timeout=10).json()
    return data.get("current")
