from workers.base_worker import BaseWorker

from weather.forecast import get_astro_forecast
from astro.astro_score import compute_astro_scores
from services.forecast_processing import build_hourly_rows


class ForecastWorker(BaseWorker):
    def __init__(self, lat: float, lon: float):
        super().__init__()
        self.lat = lat
        self.lon = lon

    def run(self):
        try:
            self.progress.emit("Descargando previsión meteorológica…")
            forecast = get_astro_forecast(self.lat, self.lon)

            self.progress.emit("Procesando datos horarios…")
            hourly = build_hourly_rows(forecast)

            self.progress.emit("Calculando AstroScore…")
            hourly, night_summary = compute_astro_scores(
                self.lat, self.lon, hourly
            )

            self.finished.emit({
                "hourly": hourly,
                "summary": night_summary
            })

        except Exception as e:
            import traceback
            print(traceback.format_exec())
            self.error.emit(str(e))
            
