import requests

def get_astro_forecast(lat, lon, days=7):
    """
    Devuelve el JSON completo (no solo hourly) para poder usar:
    - timezone (Europe/Madrid)
    - utc_offset_seconds
    - hourly (time, cloud_cover, humidity, wind...)
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=cloud_cover,relative_humidity_2m,wind_speed_10m"
        f"&forecast_days={days}"
        "&timezone=auto"
    )
    return requests.get(url, timeout=10).json()
