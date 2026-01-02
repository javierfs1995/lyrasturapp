from typing import Any, Dict, List


def build_hourly_rows(forecast: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convierte la respuesta de forecast en filas horarias normalizadas.
    Compatible con Open-Meteo.
    """
    hourly = forecast.get("hourly", {})
    if not isinstance(hourly, dict):
        return []

    times = hourly.get("time", [])

    clouds = (
        hourly.get("cloud_cover")
        or hourly.get("cloudcover")
        or []
    )

    humidity = (
        hourly.get("relative_humidity_2m")
        or hourly.get("relativehumidity_2m")
        or []
    )

    wind = (
        hourly.get("wind_speed_10m")
        or hourly.get("windspeed_10m")
        or []
    )

    rows = []
    for i in range(len(times)):
        rows.append({
            "time": times[i],
            "clouds": float(clouds[i]) if i < len(clouds) else 0.0,
            "humidity": float(humidity[i]) if i < len(humidity) else 0.0,
            "wind": float(wind[i]) if i < len(wind) else 0.0,
        })

    return rows
