"""Tests for weather data service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from city_compare.cache import LocalCache
from city_compare.models import GeoLocation, ProfileConfig
from city_compare.weather import OpenMeteoClient, WeatherError


class TestOpenMeteoClient:
    """Test Open-Meteo weather client."""

    @pytest.fixture
    def mock_cache(self, tmp_path: Path) -> LocalCache:
        """Create a temporary cache."""
        return LocalCache(tmp_path / "cache.db")

    @pytest.fixture
    def location(self) -> GeoLocation:
        """Sample location for testing."""
        return GeoLocation(
            city_name="Lille",
            lat=50.6292,
            lon=3.0573,
            display_name="Lille, Nord, France",
        )

    @pytest.fixture
    def profile(self) -> ProfileConfig:
        """Sample profile for testing."""
        return ProfileConfig(
            rain_threshold_mm=1.0,
            hot_threshold_c=30.0,
            weather_months=12,
        )

    @pytest.fixture
    def sample_api_response(self) -> dict:
        """Sample API response from Open-Meteo."""
        return {
            "daily": {
                "time": ["2025-01-01", "2025-01-02", "2025-01-03"],
                "temperature_2m_mean": [5.0, 6.0, 7.0],
                "temperature_2m_max": [8.0, 9.0, 10.0],
                "temperature_2m_min": [2.0, 3.0, 4.0],
                "precipitation_sum": [0.0, 2.5, 0.5],
            }
        }

    def test_compute_metrics(self, mock_cache: LocalCache, profile: ProfileConfig):
        """Test computing metrics from daily data."""
        client = OpenMeteoClient(cache=mock_cache)

        daily_data = {
            "temperature_2m_mean": [10.0, 12.0, 14.0, 16.0],
            "temperature_2m_max": [15.0, 18.0, 32.0, 35.0],  # 2 hot days
            "temperature_2m_min": [5.0, 6.0, 8.0, 10.0],
            "precipitation_sum": [0.0, 1.5, 0.0, 5.0],  # 2 rain days
        }

        metrics = client._compute_metrics(daily_data, profile)

        assert metrics.avg_temp_c == 13.0  # (10+12+14+16)/4
        assert metrics.rain_days == 2
        assert metrics.hot_days == 2
        assert metrics.min_temp_c == 5.0
        assert metrics.max_temp_c == 35.0

    def test_compute_metrics_handles_none_values(
        self, mock_cache: LocalCache, profile: ProfileConfig
    ):
        """Test that None values in data are handled correctly."""
        client = OpenMeteoClient(cache=mock_cache)

        daily_data = {
            "temperature_2m_mean": [10.0, None, 14.0],
            "temperature_2m_max": [15.0, None, 20.0],
            "temperature_2m_min": [5.0, None, 8.0],
            "precipitation_sum": [0.0, None, 2.0],
        }

        metrics = client._compute_metrics(daily_data, profile)

        assert metrics.avg_temp_c == 12.0  # (10+14)/2
        assert metrics.rain_days == 1

    def test_get_weather_uses_cache(
        self,
        mock_cache: LocalCache,
        location: GeoLocation,
        profile: ProfileConfig,
    ):
        """Test that cached data is used when available."""
        client = OpenMeteoClient(cache=mock_cache)

        # Pre-populate cache
        cached_data = {
            "temperature_2m_mean": [15.0],
            "temperature_2m_max": [20.0],
            "temperature_2m_min": [10.0],
            "precipitation_sum": [0.0],
        }

        # Manually set cache (we need to match the cache key pattern)
        with patch.object(mock_cache, "get", return_value=cached_data):
            metrics = client.get_weather(location, profile)

        assert metrics.avg_temp_c == 15.0

    @patch("city_compare.weather.httpx.Client")
    def test_get_weather_fetches_from_api(
        self,
        mock_client_class: MagicMock,
        mock_cache: LocalCache,
        location: GeoLocation,
        profile: ProfileConfig,
        sample_api_response: dict,
    ):
        """Test fetching weather data from API."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client_class.return_value = mock_client

        client = OpenMeteoClient(cache=mock_cache)
        metrics = client.get_weather(location, profile)

        assert metrics.avg_temp_c == 6.0  # (5+6+7)/3
        assert metrics.rain_days == 1  # only 2.5 >= 1.0 (0.5 < 1.0)
        assert metrics.hot_days == 0

    def test_weather_error_on_empty_data(self, mock_cache: LocalCache, profile: ProfileConfig):
        """Test that WeatherError is raised when no temperature data."""
        client = OpenMeteoClient(cache=mock_cache)

        daily_data = {
            "temperature_2m_mean": [],
            "temperature_2m_max": [],
            "temperature_2m_min": [],
            "precipitation_sum": [],
        }

        with pytest.raises(WeatherError, match="No temperature data"):
            client._compute_metrics(daily_data, profile)
