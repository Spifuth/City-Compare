"""Air quality data service using Open-Meteo API."""

import logging
from typing import Any, ClassVar

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .cache import LocalCache
from .models import GeoLocation

logger = logging.getLogger(__name__)


class AirQualityError(Exception):
    """Raised when air quality data retrieval fails."""

    pass


class AirQualityMetrics:
    """Air quality metrics for a city."""

    def __init__(
        self,
        aqi_avg: float,
        pm2_5_avg: float,
        pm10_avg: float,
        good_days: int,
        moderate_days: int,
        unhealthy_days: int,
    ):
        self.aqi_avg = aqi_avg  # Average European AQI (0-500)
        self.pm2_5_avg = pm2_5_avg  # Average PM2.5 (µg/m³)
        self.pm10_avg = pm10_avg  # Average PM10 (µg/m³)
        self.good_days = good_days  # Days with AQI < 50
        self.moderate_days = moderate_days  # Days with AQI 50-100
        self.unhealthy_days = unhealthy_days  # Days with AQI > 100

    @property
    def quality_label(self) -> str:
        """Return a human-readable label for average air quality."""
        if self.aqi_avg < 20:
            return "Excellent"
        elif self.aqi_avg < 40:
            return "Bon"
        elif self.aqi_avg < 60:
            return "Modéré"
        elif self.aqi_avg < 80:
            return "Médiocre"
        elif self.aqi_avg < 100:
            return "Mauvais"
        else:
            return "Très mauvais"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "aqi_avg": self.aqi_avg,
            "pm2_5_avg": self.pm2_5_avg,
            "pm10_avg": self.pm10_avg,
            "good_days": self.good_days,
            "moderate_days": self.moderate_days,
            "unhealthy_days": self.unhealthy_days,
            "quality_label": self.quality_label,
        }


class OpenMeteoAirQualityClient:
    """Client for Open-Meteo Air Quality API."""

    BASE_URL: ClassVar[str] = "https://air-quality-api.open-meteo.com/v1/air-quality"
    CACHE_TTL: ClassVar[int] = 86400 * 7  # Cache for 7 days

    def __init__(self, cache: LocalCache | None = None, verify_ssl: bool = True):
        self.cache = cache or LocalCache()
        self._verify_ssl = verify_ssl

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    def _fetch_air_quality(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch air quality data with retry logic."""
        with httpx.Client(verify=self._verify_ssl) as client:
            response = client.get(self.BASE_URL, params=params, timeout=30.0)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result

    def get_air_quality(
        self,
        location: GeoLocation,
        days: int = 30,
    ) -> AirQualityMetrics:
        """
        Get air quality metrics for a location.

        Note: Open-Meteo Air Quality API only provides forecast and recent data,
        not historical archive. We use the past 7 days + forecast for estimation.

        Args:
            location: Geographic location to query
            days: Number of past days to analyze (max ~7 for recent data)

        Returns:
            AirQualityMetrics with aggregated data
        """
        cache_key = f"airquality:{location.lat:.4f}:{location.lon:.4f}:{days}"

        # Check cache
        cached = self.cache.get(cache_key)
        if cached is not None:
            return self._build_metrics(cached)

        # Fetch from API - request past days
        params = {
            "latitude": location.lat,
            "longitude": location.lon,
            "hourly": "european_aqi,pm2_5,pm10",
            "past_days": min(days, 7),  # API limits to recent data
            "forecast_days": 1,
        }

        try:
            logger.debug(f"Fetching air quality for {location.lat:.4f}, {location.lon:.4f}")
            data = self._fetch_air_quality(params)
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching air quality data: {e}")
            raise AirQualityError(f"HTTP error fetching air quality data: {e}") from e

        if "hourly" not in data:
            raise AirQualityError(f"Invalid response from Open-Meteo Air Quality: {data}")

        # Cache the raw data
        self.cache.set(cache_key, data["hourly"], ttl_seconds=self.CACHE_TTL)

        return self._build_metrics(data["hourly"])

    def _build_metrics(self, hourly_data: dict[str, Any]) -> AirQualityMetrics:
        """Build metrics from hourly data."""
        # Filter out None values
        aqi_values = [v for v in hourly_data.get("european_aqi", []) if v is not None]
        pm2_5_values = [v for v in hourly_data.get("pm2_5", []) if v is not None]
        pm10_values = [v for v in hourly_data.get("pm10", []) if v is not None]

        if not aqi_values:
            raise AirQualityError("No air quality data available")

        # Calculate averages
        aqi_avg = sum(aqi_values) / len(aqi_values)
        pm2_5_avg = sum(pm2_5_values) / len(pm2_5_values) if pm2_5_values else 0
        pm10_avg = sum(pm10_values) / len(pm10_values) if pm10_values else 0

        # Count days by quality (group hourly into daily, then count)
        # Simplify: use hourly data grouped by 24h blocks
        hours_per_day = 24
        num_days = len(aqi_values) // hours_per_day

        good_days = 0
        moderate_days = 0
        unhealthy_days = 0

        for day_idx in range(max(1, num_days)):
            start = day_idx * hours_per_day
            end = start + hours_per_day
            day_values = aqi_values[start:end]
            if day_values:
                day_avg = sum(day_values) / len(day_values)
                if day_avg < 50:
                    good_days += 1
                elif day_avg < 100:
                    moderate_days += 1
                else:
                    unhealthy_days += 1

        return AirQualityMetrics(
            aqi_avg=round(aqi_avg, 1),
            pm2_5_avg=round(pm2_5_avg, 1),
            pm10_avg=round(pm10_avg, 1),
            good_days=good_days,
            moderate_days=moderate_days,
            unhealthy_days=unhealthy_days,
        )
