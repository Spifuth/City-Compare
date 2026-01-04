"""Geocoding service using Nominatim (OpenStreetMap)."""

import ssl
import time
from typing import ClassVar

import httpx

from .cache import LocalCache
from .models import GeoLocation


class GeocodingError(Exception):
    """Raised when geocoding fails."""

    pass


class NominatimGeocoder:
    """Geocoder using Nominatim API with caching and rate limiting."""

    BASE_URL: ClassVar[str] = "https://nominatim.openstreetmap.org/search"
    USER_AGENT: ClassVar[str] = "city-compare/0.1.0 (https://github.com/user/city-compare)"
    MIN_REQUEST_INTERVAL: ClassVar[float] = 1.0  # Nominatim requires 1 req/s max

    def __init__(self, cache: LocalCache | None = None, verify_ssl: bool = True):
        self.cache = cache or LocalCache()
        self._last_request_time: float = 0
        self._verify_ssl = verify_ssl

    def _rate_limit(self) -> None:
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def geocode(self, city_name: str, country: str = "France") -> GeoLocation:
        """
        Geocode a city name to coordinates.

        Args:
            city_name: Name of the city to geocode
            country: Country to search in (default: France)

        Returns:
            GeoLocation with coordinates

        Raises:
            GeocodingError: If the city cannot be found
        """
        cache_key = f"geocode:{city_name.lower()}:{country.lower()}"

        # Check cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            return GeoLocation(
                city_name=city_name,
                lat=cached["lat"],
                lon=cached["lon"],
                display_name=cached["display_name"],
            )

        # Rate limit before making request
        self._rate_limit()

        # Make API request
        params = {
            "q": f"{city_name}, {country}",
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
            "featuretype": "city",
        }

        headers = {"User-Agent": self.USER_AGENT}

        try:
            with httpx.Client(verify=self._verify_ssl) as client:
                response = client.get(self.BASE_URL, params=params, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as e:
            raise GeocodingError(f"HTTP error during geocoding: {e}") from e

        if not data:
            raise GeocodingError(
                f"Ville '{city_name}' non trouvée. "
                "Vérifiez l'orthographe ou utilisez le nom officiel de la commune."
            )

        result = data[0]
        lat = float(result["lat"])
        lon = float(result["lon"])
        display_name = result.get("display_name", city_name)

        # Cache the result (indefinitely for geocoding)
        self.cache.set(cache_key, {"lat": lat, "lon": lon, "display_name": display_name})

        return GeoLocation(
            city_name=city_name,
            lat=lat,
            lon=lon,
            display_name=display_name,
        )
