"""Tests for geocoding service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from city_compare.cache import LocalCache
from city_compare.geocoding import NominatimGeocoder, GeocodingError


class TestNominatimGeocoder:
    """Test Nominatim geocoding service."""

    @pytest.fixture
    def mock_cache(self, tmp_path: Path) -> LocalCache:
        """Create a temporary cache."""
        return LocalCache(tmp_path / "cache.db")

    @pytest.fixture
    def sample_api_response(self) -> list:
        """Sample API response from Nominatim."""
        return [
            {
                "lat": "50.6292",
                "lon": "3.0573",
                "display_name": "Lille, Nord, Hauts-de-France, France",
                "address": {"city": "Lille", "county": "Nord"},
            }
        ]

    def test_geocode_uses_cache(self, mock_cache: LocalCache):
        """Test that cached results are used."""
        geocoder = NominatimGeocoder(cache=mock_cache)

        # Pre-populate cache
        mock_cache.set(
            "geocode:lille:france",
            {"lat": 50.6292, "lon": 3.0573, "display_name": "Lille, France"},
        )

        result = geocoder.geocode("Lille")

        assert result.city_name == "Lille"
        assert result.lat == 50.6292
        assert result.lon == 3.0573

    @patch("city_compare.geocoding.httpx.Client")
    def test_geocode_fetches_from_api(
        self,
        mock_client_class: MagicMock,
        mock_cache: LocalCache,
        sample_api_response: list,
    ):
        """Test fetching geocoding data from API."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.json.return_value = sample_api_response
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client_class.return_value = mock_client

        geocoder = NominatimGeocoder(cache=mock_cache)
        result = geocoder.geocode("Lille")

        assert result.city_name == "Lille"
        assert result.lat == 50.6292
        assert result.lon == 3.0573
        assert "Lille" in result.display_name

    @patch("city_compare.geocoding.httpx.Client")
    def test_geocode_city_not_found(
        self,
        mock_client_class: MagicMock,
        mock_cache: LocalCache,
    ):
        """Test error when city is not found."""
        # Setup mock to return empty list
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)
        mock_client_class.return_value = mock_client

        geocoder = NominatimGeocoder(cache=mock_cache)

        with pytest.raises(GeocodingError, match="non trouvée"):
            geocoder.geocode("VilleInexistante12345")

    def test_rate_limiting(self, mock_cache: LocalCache):
        """Test that rate limiting delays requests."""
        geocoder = NominatimGeocoder(cache=mock_cache)

        # Simulate a recent request
        import time
        geocoder._last_request_time = time.time()

        start = time.time()
        geocoder._rate_limit()
        elapsed = time.time() - start

        # Should have waited approximately 1 second
        assert elapsed >= 0.9

    def test_cache_key_is_case_insensitive(self, mock_cache: LocalCache):
        """Test that cache keys are normalized to lowercase."""
        geocoder = NominatimGeocoder(cache=mock_cache)

        # Pre-populate cache with lowercase key
        mock_cache.set(
            "geocode:paris:france",
            {"lat": 48.8566, "lon": 2.3522, "display_name": "Paris, France"},
        )

        # Query with different case
        result = geocoder.geocode("PARIS")

        assert result.city_name == "PARIS"
        assert result.lat == 48.8566

    def test_user_agent_is_set(self):
        """Test that the User-Agent is properly configured."""
        assert "city-compare" in NominatimGeocoder.USER_AGENT
        assert "Spifuth" in NominatimGeocoder.USER_AGENT

