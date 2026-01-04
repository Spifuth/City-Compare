"""Weather data service using Open-Meteo archive API."""

import logging
from datetime import date, timedelta
from typing import ClassVar

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .cache import LocalCache
from .models import GeoLocation, ProfileConfig, WeatherMetrics

logger = logging.getLogger(__name__)


class WeatherError(Exception):
    """Raised when weather data retrieval fails."""

    pass


class OpenMeteoClient:
    """Client for Open-Meteo historical weather API."""

    BASE_URL: ClassVar[str] = "https://archive-api.open-meteo.com/v1/archive"
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
    def _fetch_weather(self, params: dict) -> dict:
        """Fetch weather data with retry logic."""
        with httpx.Client(verify=self._verify_ssl) as client:
            response = client.get(self.BASE_URL, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()

    def get_weather(
        self,
        location: GeoLocation,
        profile: ProfileConfig,
    ) -> WeatherMetrics:
        """
        Get weather metrics for a location over the past N months.

        Args:
            location: Geographic location to query
            profile: Profile with thresholds and time window

        Returns:
            WeatherMetrics with aggregated data
        """
        # Calculate date range (last N months)
        end_date = date.today() - timedelta(days=1)  # Yesterday (data availability)
        start_date = end_date - timedelta(days=profile.weather_months * 30)

        cache_key = (
            f"weather:{location.lat:.4f}:{location.lon:.4f}:"
            f"{start_date.isoformat()}:{end_date.isoformat()}"
        )

        # Check cache
        cached = self.cache.get(cache_key)
        if cached is not None:
            return self._compute_metrics(cached, profile)

        # Fetch from API
        params = {
            "latitude": location.lat,
            "longitude": location.lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum",
            "timezone": "Europe/Paris",
        }

        try:
            logger.debug(f"Fetching weather for {location.lat:.4f}, {location.lon:.4f}")
            data = self._fetch_weather(params)
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching weather data: {e}")
            raise WeatherError(f"HTTP error fetching weather data: {e}") from e

        if "daily" not in data:
            raise WeatherError(f"Invalid response from Open-Meteo: {data}")

        # Cache the raw data
        self.cache.set(cache_key, data["daily"], ttl_seconds=self.CACHE_TTL)

        return self._compute_metrics(data["daily"], profile)

    def _compute_metrics(
        self,
        daily_data: dict,
        profile: ProfileConfig,
    ) -> WeatherMetrics:
        """Compute metrics from daily weather data."""
        temps_mean = [t for t in daily_data["temperature_2m_mean"] if t is not None]
        temps_max = [t for t in daily_data["temperature_2m_max"] if t is not None]
        temps_min = [t for t in daily_data["temperature_2m_min"] if t is not None]
        precip = [p for p in daily_data["precipitation_sum"] if p is not None]

        if not temps_mean:
            raise WeatherError("No temperature data available")

        avg_temp = sum(temps_mean) / len(temps_mean)
        rain_days = sum(1 for p in precip if p >= profile.rain_threshold_mm)
        hot_days = sum(1 for t in temps_max if t >= profile.hot_threshold_c)
        total_precip = sum(precip)

        return WeatherMetrics(
            avg_temp_c=round(avg_temp, 1),
            rain_days=rain_days,
            hot_days=hot_days,
            total_precip_mm=round(total_precip, 1),
            min_temp_c=round(min(temps_min), 1) if temps_min else 0.0,
            max_temp_c=round(max(temps_max), 1) if temps_max else 0.0,
        )
