"""Integration tests for the CLI."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from city_compare.cli import app
from city_compare.models import GeoLocation, WeatherMetrics

runner = CliRunner()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_rent_csv(temp_dir: Path) -> Path:
    """Create a mock rent CSV file."""
    csv_path = temp_dir / "loyers.csv"
    csv_path.write_text(
        """commune,loyer_med,departement
Lille,12.5,59
Nantes,11.8,44
Lyon,14.2,69
Bordeaux,13.0,33
Toulouse,11.5,31
Marseille,12.0,13
"""
    )
    return csv_path


@pytest.fixture
def mock_profile(temp_dir: Path, mock_rent_csv: Path) -> Path:
    """Create a mock profile file."""
    profile_path = temp_dir / "profile.yml"
    profile_path.write_text(
        f"""
rain_threshold_mm: 1.0
hot_threshold_c: 30.0
weather_months: 12
rent_csv_path: "{mock_rent_csv}"
"""
    )
    return profile_path


@pytest.fixture
def mock_rules(temp_dir: Path) -> Path:
    """Create a mock rules file."""
    rules_path = temp_dir / "rules.rules"
    rules_path.write_text(
        """
# Simple test rules
rent_score = 100 - rent_m2 * 2
weather_score = avg_temp_c * 2 - rain_days
score = rent_score + weather_score
"""
    )
    return rules_path


class TestCLICompare:
    """Test the compare command."""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_two_cities(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test comparing two cities."""
        # Setup mocks
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.side_effect = [
            GeoLocation("Lille", 50.6292, 3.0573, "Lille, France"),
            GeoLocation("Nantes", 47.2184, -1.5536, "Nantes, France"),
        ]
        mock_geocoder_class.return_value = mock_geocoder

        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = WeatherMetrics(
            avg_temp_c=12.0,
            rain_days=100,
            hot_days=10,
            total_precip_mm=800.0,
            min_temp_c=-5.0,
            max_temp_c=35.0,
        )
        mock_weather_class.return_value = mock_weather

        output_path = temp_dir / "report.md"
        json_path = temp_dir / "summary.json"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lille",
                "Nantes",
                "--profile",
                str(mock_profile),
                "--rules",
                str(mock_rules),
                "--out",
                str(output_path),
                "--json",
                str(json_path),
            ],
        )

        assert result.exit_code == 0
        assert output_path.exists()
        assert json_path.exists()

        # Check report content
        report = output_path.read_text()
        assert "Lille" in report
        assert "Nantes" in report
        assert "Score" in report

        # Check JSON content
        with open(json_path) as f:
            data = json.load(f)
        assert "Lille" in data["cities"]
        assert "Nantes" in data["cities"]
        assert "winner" in data

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_multiple_cities(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test comparing more than 2 cities."""
        # Setup mocks
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.side_effect = [
            GeoLocation("Lille", 50.6292, 3.0573, "Lille, France"),
            GeoLocation("Nantes", 47.2184, -1.5536, "Nantes, France"),
            GeoLocation("Lyon", 45.7640, 4.8357, "Lyon, France"),
        ]
        mock_geocoder_class.return_value = mock_geocoder

        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = WeatherMetrics(
            avg_temp_c=12.0,
            rain_days=100,
            hot_days=10,
            total_precip_mm=800.0,
            min_temp_c=-5.0,
            max_temp_c=35.0,
        )
        mock_weather_class.return_value = mock_weather

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lille",
                "Nantes",
                "Lyon",
                "--profile",
                str(mock_profile),
                "--rules",
                str(mock_rules),
                "--out",
                str(output_path),
            ],
        )

        assert result.exit_code == 0
        assert output_path.exists()

        # Check report content has ranking
        report = output_path.read_text()
        assert "Classement" in report
        assert "🥇" in report or "1." in report

    def test_compare_requires_two_cities(self, temp_dir: Path):
        """Test that compare requires at least 2 cities."""
        result = runner.invoke(
            app,
            [
                "compare",
                "Lille",  # Only one city
            ],
        )

        assert result.exit_code == 1
        assert "2 villes" in result.output

    def test_compare_missing_profile(self, temp_dir: Path):
        """Test error when profile file is missing."""
        result = runner.invoke(
            app,
            [
                "compare",
                "Lille",
                "Nantes",
                "--profile",
                str(temp_dir / "nonexistent.yml"),
            ],
        )

        assert result.exit_code == 1
        assert "introuvable" in result.output.lower()


class TestCLIClearCache:
    """Test the clear-cache command."""

    def test_clear_cache(self, temp_dir: Path):
        """Test clearing the cache."""
        # Create a cache
        from city_compare.cache import LocalCache

        cache_path = temp_dir / "cache.db"
        cache = LocalCache(cache_path)
        cache.set("test_key", "test_value")

        # Verify it was set
        assert cache.get("test_key") == "test_value"

        # Clear it
        cache.clear()

        # Verify it was cleared
        assert cache.get("test_key") is None


class TestCLIVersion:
    """Test the version command."""

    def test_version_flag(self):
        """Test --version flag."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "city-compare" in result.output.lower()
        assert "version" in result.output.lower()


class TestCLIAirQuality:
    """Test air quality integration in CLI."""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    @patch("city_compare.cli.OpenMeteoAirQualityClient")
    def test_compare_with_air_quality(
        self,
        mock_air_class: MagicMock,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test comparing cities with air quality data."""
        from city_compare.air_quality import AirQualityMetrics

        # Setup mocks
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.side_effect = [
            GeoLocation("Lille", 50.6292, 3.0573, "Lille, France"),
            GeoLocation("Nantes", 47.2184, -1.5536, "Nantes, France"),
        ]
        mock_geocoder_class.return_value = mock_geocoder

        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = WeatherMetrics(
            avg_temp_c=12.0,
            rain_days=100,
            hot_days=10,
            total_precip_mm=800.0,
            min_temp_c=-5.0,
            max_temp_c=35.0,
        )
        mock_weather_class.return_value = mock_weather

        mock_air = MagicMock()
        mock_air.get_air_quality.return_value = AirQualityMetrics(
            aqi_avg=45.0,
            pm2_5_avg=12.0,
            pm10_avg=25.0,
            good_days=200,
            moderate_days=100,
            unhealthy_days=65,
        )
        mock_air_class.return_value = mock_air

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lille",
                "Nantes",
                "--profile",
                str(mock_profile),
                "--rules",
                str(mock_rules),
                "--out",
                str(output_path),
                "--air-quality",
            ],
        )

        assert result.exit_code == 0
        assert output_path.exists()

        # Verify air quality client was created and called
        mock_air_class.assert_called_once()
        assert mock_air.get_air_quality.call_count == 2


class TestCLIExplain:
    """Test explain mode in CLI."""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_with_explain(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test comparing cities with explanation enabled."""
        # Setup mocks
        mock_geocoder = MagicMock()
        mock_geocoder.geocode.side_effect = [
            GeoLocation("Lille", 50.6292, 3.0573, "Lille, France"),
            GeoLocation("Nantes", 47.2184, -1.5536, "Nantes, France"),
        ]
        mock_geocoder_class.return_value = mock_geocoder

        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = WeatherMetrics(
            avg_temp_c=12.0,
            rain_days=100,
            hot_days=10,
            total_precip_mm=800.0,
            min_temp_c=-5.0,
            max_temp_c=35.0,
        )
        mock_weather_class.return_value = mock_weather

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lille",
                "Nantes",
                "--profile",
                str(mock_profile),
                "--rules",
                str(mock_rules),
                "--out",
                str(output_path),
                "--explain",
            ],
        )

        assert result.exit_code == 0
        assert output_path.exists()

        # Check report contains explanation
        report = output_path.read_text()
        assert "rent_score" in report or "weather_score" in report


class TestCLIErrors:
    """Test error handling in CLI."""

    @patch("city_compare.cli.NominatimGeocoder")
    def test_geocoding_error(
        self,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test handling of geocoding errors."""
        from city_compare.geocoding import GeocodingError

        mock_geocoder = MagicMock()
        mock_geocoder.geocode.side_effect = GeocodingError("City not found")
        mock_geocoder_class.return_value = mock_geocoder

        result = runner.invoke(
            app,
            [
                "compare",
                "VilleInexistante",
                "Nantes",
                "--profile",
                str(mock_profile),
                "--rules",
                str(mock_rules),
            ],
        )

        assert result.exit_code == 1
        assert "Erreur" in result.output

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_weather_error(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test handling of weather API errors."""
        from city_compare.weather import WeatherError

        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = GeoLocation("Lille", 50.6292, 3.0573, "Lille, France")
        mock_geocoder_class.return_value = mock_geocoder

        mock_weather = MagicMock()
        mock_weather.get_weather.side_effect = WeatherError("API unavailable")
        mock_weather_class.return_value = mock_weather

        result = runner.invoke(
            app,
            [
                "compare",
                "Lille",
                "Nantes",
                "--profile",
                str(mock_profile),
                "--rules",
                str(mock_rules),
            ],
        )

        assert result.exit_code == 1
        assert "Erreur" in result.output

    def test_invalid_rules_file(self, temp_dir: Path, mock_profile: Path):
        """Test handling of invalid rules file."""
        bad_rules = temp_dir / "bad.rules"
        bad_rules.write_text("this is not valid = syntax !!!")

        result = runner.invoke(
            app,
            [
                "compare",
                "Lille",
                "Nantes",
                "--profile",
                str(mock_profile),
                "--rules",
                str(bad_rules),
            ],
        )

        assert result.exit_code == 1
        assert "règles" in result.output.lower() or "Erreur" in result.output
