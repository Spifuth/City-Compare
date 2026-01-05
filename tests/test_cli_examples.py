"""
Comprehensive integration tests for all CLI examples.

These tests cover all 20 documented usage examples of the city-compare CLI,
ensuring each command produces the expected output.
"""

import json
import re
import socket
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from city_compare.cli import app
from city_compare.models import GeoLocation, WeatherMetrics

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════════════


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
Lyon,14.2,69
Bordeaux,13.0,33
Nantes,11.8,44
Lille,12.5,59
Toulouse,11.5,31
Marseille,12.0,13
Paris,28.0,75
Nice,16.5,06
Brest,9.5,29
Montpellier,14.0,34
Angers,10.5,49
Rennes,12.2,35
Grenoble,11.0,38
Strasbourg,12.8,67
"""
    )
    return csv_path


@pytest.fixture
def mock_profile(temp_dir: Path, mock_rent_csv: Path) -> Path:
    """Create a mock default profile file."""
    profile_path = temp_dir / "default.yml"
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
def mock_sunny_profile(temp_dir: Path, mock_rent_csv: Path) -> Path:
    """Create a mock sunny profile file."""
    profile_path = temp_dir / "sunny.yml"
    profile_path.write_text(
        f"""
rain_threshold_mm: 0.5
hot_threshold_c: 28.0
weather_months: 12
rent_csv_path: "{mock_rent_csv}"
ideal_temp_c: 22.0
"""
    )
    return profile_path


@pytest.fixture
def mock_budget_profile(temp_dir: Path, mock_rent_csv: Path) -> Path:
    """Create a mock budget profile file."""
    profile_path = temp_dir / "budget.yml"
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
def mock_retraite_profile(temp_dir: Path, mock_rent_csv: Path) -> Path:
    """Create a mock retraite profile file."""
    profile_path = temp_dir / "retraite.yml"
    profile_path.write_text(
        f"""
rain_threshold_mm: 1.0
hot_threshold_c: 30.0
weather_months: 12
rent_csv_path: "{mock_rent_csv}"
ideal_temp_c: 18.0
"""
    )
    return profile_path


@pytest.fixture
def mock_qualite_vie_profile(temp_dir: Path, mock_rent_csv: Path) -> Path:
    """Create a mock qualite_vie profile file."""
    profile_path = temp_dir / "qualite_vie.yml"
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
    """Create a mock default rules file."""
    rules_path = temp_dir / "default.rules"
    rules_path.write_text(
        """
# Default rules for testing
rent_m2 < 10 => bonus(15)
rent_m2 >= 10 and rent_m2 < 15 => bonus(5)
rent_m2 > 20 => penalty(10)
rent_m2 > 25 => penalty(15)

avg_temp >= 12 and avg_temp <= 18 => bonus(5)
rain_days < 120 => bonus(5)

score = total_bonus - total_penalty
"""
    )
    return rules_path


@pytest.fixture
def mock_budget_rules(temp_dir: Path) -> Path:
    """Create mock budget rules file."""
    rules_path = temp_dir / "budget.rules"
    rules_path.write_text(
        """
# Budget-focused rules
rent_m2 < 10 => bonus(25)
rent_m2 >= 10 and rent_m2 < 12 => bonus(15)
rent_m2 >= 12 and rent_m2 < 15 => bonus(5)
rent_m2 > 18 => penalty(15)
rent_m2 > 25 => penalty(25)

score = total_bonus - total_penalty
"""
    )
    return rules_path


@pytest.fixture
def mock_retraite_rules(temp_dir: Path) -> Path:
    """Create mock retraite rules file."""
    rules_path = temp_dir / "retraite.rules"
    rules_path.write_text(
        """
# Retraite rules - mild weather, affordable
rent_m2 < 12 => bonus(10)
avg_temp >= 14 and avg_temp <= 20 => bonus(15)
rain_days < 100 => bonus(10)
hot_days < 30 => bonus(5)

score = total_bonus - total_penalty
"""
    )
    return rules_path


@pytest.fixture
def mock_weather_priority_rules(temp_dir: Path) -> Path:
    """Create mock weather priority rules file."""
    rules_path = temp_dir / "weather_priority.rules"
    rules_path.write_text(
        """
# Weather-focused rules
rain_days < 80 => bonus(20)
rain_days < 100 => bonus(10)
rain_days > 150 => penalty(15)

avg_temp >= 15 => bonus(10)
hot_days < 20 => bonus(5)

score = total_bonus - total_penalty
"""
    )
    return rules_path


def create_mock_geocoder():
    """Create a mock geocoder that returns predefined locations."""
    mock = MagicMock()
    locations = {
        "Lyon": GeoLocation("Lyon", 45.7640, 4.8357, "Lyon, Rhône, France"),
        "Bordeaux": GeoLocation("Bordeaux", 44.8378, -0.5792, "Bordeaux, Gironde, France"),
        "Nantes": GeoLocation("Nantes", 47.2184, -1.5536, "Nantes, Loire-Atlantique, France"),
        "Lille": GeoLocation("Lille", 50.6292, 3.0573, "Lille, Nord, France"),
        "Toulouse": GeoLocation("Toulouse", 43.6047, 1.4442, "Toulouse, Haute-Garonne, France"),
        "Marseille": GeoLocation("Marseille", 43.2965, 5.3698, "Marseille, Bouches-du-Rhône, France"),
        "Paris": GeoLocation("Paris", 48.8566, 2.3522, "Paris, Île-de-France, France"),
        "Nice": GeoLocation("Nice", 43.7102, 7.2620, "Nice, Alpes-Maritimes, France"),
        "Brest": GeoLocation("Brest", 48.3904, -4.4861, "Brest, Finistère, France"),
        "Montpellier": GeoLocation("Montpellier", 43.6108, 3.8767, "Montpellier, Hérault, France"),
        "Angers": GeoLocation("Angers", 47.4784, -0.5632, "Angers, Maine-et-Loire, France"),
        "Rennes": GeoLocation("Rennes", 48.1173, -1.6778, "Rennes, Ille-et-Vilaine, France"),
        "Grenoble": GeoLocation("Grenoble", 45.1885, 5.7245, "Grenoble, Isère, France"),
        "Strasbourg": GeoLocation("Strasbourg", 48.5734, 7.7521, "Strasbourg, Bas-Rhin, France"),
    }

    def geocode_side_effect(city_name):
        return locations.get(city_name, locations["Lyon"])

    mock.geocode.side_effect = geocode_side_effect
    return mock


def create_mock_weather_client():
    """Create a mock weather client with predefined metrics."""
    mock = MagicMock()
    weather_data = {
        "Lyon": WeatherMetrics(avg_temp_c=13.4, rain_days=114, hot_days=43, total_precip_mm=898.6, min_temp_c=-6.9, max_temp_c=39.7),
        "Bordeaux": WeatherMetrics(avg_temp_c=14.2, rain_days=121, hot_days=35, total_precip_mm=944.0, min_temp_c=-4.5, max_temp_c=38.2),
        "Nantes": WeatherMetrics(avg_temp_c=13.5, rain_days=119, hot_days=21, total_precip_mm=783.2, min_temp_c=-3.2, max_temp_c=36.5),
        "Lille": WeatherMetrics(avg_temp_c=11.9, rain_days=103, hot_days=9, total_precip_mm=742.0, min_temp_c=-5.1, max_temp_c=33.8),
        "Toulouse": WeatherMetrics(avg_temp_c=14.8, rain_days=98, hot_days=48, total_precip_mm=656.0, min_temp_c=-3.8, max_temp_c=40.1),
        "Marseille": WeatherMetrics(avg_temp_c=16.1, rain_days=67, hot_days=52, total_precip_mm=524.0, min_temp_c=-1.2, max_temp_c=38.9),
        "Paris": WeatherMetrics(avg_temp_c=12.8, rain_days=111, hot_days=18, total_precip_mm=637.0, min_temp_c=-4.8, max_temp_c=36.2),
        "Nice": WeatherMetrics(avg_temp_c=17.2, rain_days=63, hot_days=45, total_precip_mm=733.0, min_temp_c=1.5, max_temp_c=34.8),
        "Brest": WeatherMetrics(avg_temp_c=12.1, rain_days=168, hot_days=2, total_precip_mm=1126.0, min_temp_c=-2.1, max_temp_c=29.5),
        "Montpellier": WeatherMetrics(avg_temp_c=16.5, rain_days=56, hot_days=58, total_precip_mm=629.0, min_temp_c=-2.0, max_temp_c=39.5),
        "Angers": WeatherMetrics(avg_temp_c=12.8, rain_days=112, hot_days=15, total_precip_mm=694.0, min_temp_c=-4.2, max_temp_c=35.8),
        "Rennes": WeatherMetrics(avg_temp_c=12.4, rain_days=128, hot_days=8, total_precip_mm=712.0, min_temp_c=-3.8, max_temp_c=34.2),
        "Grenoble": WeatherMetrics(avg_temp_c=12.6, rain_days=102, hot_days=38, total_precip_mm=934.0, min_temp_c=-8.2, max_temp_c=38.5),
        "Strasbourg": WeatherMetrics(avg_temp_c=11.5, rain_days=109, hot_days=25, total_precip_mm=605.0, min_temp_c=-9.5, max_temp_c=37.8),
    }

    def get_weather_side_effect(geo, config):
        return weather_data.get(geo.city_name, weather_data["Lyon"])

    mock.get_weather.side_effect = get_weather_side_effect
    return mock


def create_mock_air_client():
    """Create a mock air quality client."""
    from city_compare.air_quality import AirQualityMetrics

    mock = MagicMock()
    mock.get_air_quality.return_value = AirQualityMetrics(
        aqi_avg=45.0,
        pm2_5_avg=12.0,
        pm10_avg=25.0,
        good_days=200,
        moderate_days=100,
        unhealthy_days=65,
    )
    return mock


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 1: Simple comparison of 2 cities
# ═══════════════════════════════════════════════════════════════════


class TestExample01SimpleTwoCities:
    """Example 1: city-compare compare "Lyon" "Bordeaux" """

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_two_cities_basic(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test basic comparison of two cities."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lyon",
                "Bordeaux",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
            ],
        )

        # Verify exit code
        assert result.exit_code == 0

        # Verify console output structure
        assert "Comparaison: Lyon vs Bordeaux" in result.output
        assert "Classement:" in result.output
        assert "🥇" in result.output
        assert "🥈" in result.output
        assert "Lyon" in result.output
        assert "Bordeaux" in result.output
        assert "Rapport généré" in result.output

        # Verify report file exists and has content
        assert output_path.exists()
        report = output_path.read_text()
        assert "Lyon" in report
        assert "Bordeaux" in report
        assert "Score" in report


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 2: Compare 3 cities
# ═══════════════════════════════════════════════════════════════════


class TestExample02ThreeCities:
    """Example 2: city-compare compare "Lyon" "Bordeaux" "Nantes" """

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_three_cities(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test comparison of three cities."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lyon",
                "Bordeaux",
                "Nantes",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
            ],
        )

        assert result.exit_code == 0
        assert "Comparaison: Lyon vs Bordeaux vs Nantes" in result.output
        assert "Classement:" in result.output
        assert "🥇" in result.output
        assert "🥈" in result.output
        assert "🥉" in result.output

        # Report should have all three cities
        report = output_path.read_text()
        assert "Lyon" in report
        assert "Bordeaux" in report
        assert "Nantes" in report


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 3: Compare 4+ cities (shows ranking with medals)
# ═══════════════════════════════════════════════════════════════════


class TestExample03FourPlusCities:
    """Example 3: city-compare compare "Paris" "Lyon" "Marseille" "Toulouse" "Nice" """

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_five_cities_with_ranking(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test comparison of 5 cities shows full ranking."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Paris",
                "Lyon",
                "Marseille",
                "Toulouse",
                "Nice",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
            ],
        )

        assert result.exit_code == 0

        # Check ranking display
        assert "Classement:" in result.output
        assert "🥇" in result.output
        assert "🥈" in result.output
        assert "🥉" in result.output
        assert "4." in result.output  # 4th place uses number
        assert "5." in result.output  # 5th place uses number

        # Verify all cities appear in ranking
        for city in ["Paris", "Lyon", "Marseille", "Toulouse", "Nice"]:
            assert city in result.output


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 4: Use a specific profile (budget-focused)
# ═══════════════════════════════════════════════════════════════════


class TestExample04BudgetProfile:
    """Example 4: city-compare compare "Lille" "Rennes" --profile profiles/budget.yml"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_with_budget_profile(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_budget_profile: Path,
        mock_budget_rules: Path,
    ):
        """Test comparison using budget profile."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lille",
                "Rennes",
                "--profile", str(mock_budget_profile),
                "--rules", str(mock_budget_rules),
                "--out", str(output_path),
            ],
        )

        assert result.exit_code == 0
        assert "Lille" in result.output
        assert "Rennes" in result.output
        assert "Classement:" in result.output


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 5: Use sunny weather profile
# ═══════════════════════════════════════════════════════════════════


class TestExample05SunnyProfile:
    """Example 5: city-compare compare "Nice" "Brest" -p profiles/sunny.yml"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_with_sunny_profile_short_flag(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_sunny_profile: Path,
        mock_rules: Path,
    ):
        """Test comparison using sunny profile with short -p flag."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Nice",
                "Brest",
                "-p", str(mock_sunny_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
            ],
        )

        assert result.exit_code == 0
        assert "Nice" in result.output
        assert "Brest" in result.output
        assert "Classement:" in result.output


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 6: Use retirement profile with its rules
# ═══════════════════════════════════════════════════════════════════


class TestExample06RetraiteProfileAndRules:
    """Example 6: city-compare compare "Montpellier" "Angers" --profile profiles/retraite.yml --rules profiles/retraite.rules"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_with_retraite_profile_and_rules(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_retraite_profile: Path,
        mock_retraite_rules: Path,
    ):
        """Test comparison using retraite profile and rules."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Montpellier",
                "Angers",
                "--profile", str(mock_retraite_profile),
                "--rules", str(mock_retraite_rules),
                "--out", str(output_path),
            ],
        )

        assert result.exit_code == 0
        assert "Montpellier" in result.output
        assert "Angers" in result.output
        assert output_path.exists()


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 7: Mix profile and different rules (short flags)
# ═══════════════════════════════════════════════════════════════════


class TestExample07MixedProfileAndRulesShortFlags:
    """Example 7: city-compare compare "Strasbourg" "Toulouse" -p profiles/qualite_vie.yml -r profiles/weather_priority.rules"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_compare_mixed_profile_rules_short_flags(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_qualite_vie_profile: Path,
        mock_weather_priority_rules: Path,
    ):
        """Test comparison with mixed profile and rules using short flags."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Strasbourg",
                "Toulouse",
                "-p", str(mock_qualite_vie_profile),
                "-r", str(mock_weather_priority_rules),
                "--out", str(output_path),
            ],
        )

        assert result.exit_code == 0
        assert "Strasbourg" in result.output
        assert "Toulouse" in result.output


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 8: Specify custom output path for markdown report
# ═══════════════════════════════════════════════════════════════════


class TestExample08CustomOutputPath:
    """Example 8: city-compare compare "Lyon" "Grenoble" --out comparaison_lyon_grenoble.md"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_custom_markdown_output_path(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test custom output path for markdown report."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        custom_output = temp_dir / "comparaison_lyon_grenoble.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lyon",
                "Grenoble",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(custom_output),
            ],
        )

        assert result.exit_code == 0
        assert f"Rapport généré: {custom_output}" in result.output
        assert custom_output.exists()

        # Verify file name in the output path
        assert custom_output.name == "comparaison_lyon_grenoble.md"


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 9: Generate JSON summary
# ═══════════════════════════════════════════════════════════════════


class TestExample09JSONOutput:
    """Example 9: city-compare compare "Nantes" "Bordeaux" --json summary.json"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_json_output_generation(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test JSON summary generation."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"
        json_path = temp_dir / "summary.json"

        result = runner.invoke(
            app,
            [
                "compare",
                "Nantes",
                "Bordeaux",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
                "--json", str(json_path),
            ],
        )

        assert result.exit_code == 0
        assert "JSON généré" in result.output
        assert json_path.exists()

        # Validate JSON structure
        with open(json_path) as f:
            data = json.load(f)

        assert "generated_at" in data
        assert "cities" in data
        assert "Nantes" in data["cities"]
        assert "Bordeaux" in data["cities"]
        assert "winner" in data

        # Validate city data structure
        nantes_data = data["cities"]["Nantes"]
        assert "city_name" in nantes_data
        assert "location" in nantes_data
        assert "metrics" in nantes_data
        assert "score" in nantes_data
        assert "scoring_variables" in nantes_data

        # Validate metrics
        assert "rent_m2" in nantes_data["metrics"]
        assert "avg_temp_c" in nantes_data["metrics"]
        assert "rain_days" in nantes_data["metrics"]


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 10: Generate HTML report with charts
# ═══════════════════════════════════════════════════════════════════


class TestExample10HTMLOutput:
    """Example 10: city-compare compare "Marseille" "Nice" "Montpellier" --html rapport.html"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_html_report_generation(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test HTML report generation with full structure validation."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"
        html_path = temp_dir / "rapport.html"

        result = runner.invoke(
            app,
            [
                "compare",
                "Marseille",
                "Nice",
                "Montpellier",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
                "--html", str(html_path),
            ],
        )

        assert result.exit_code == 0
        assert "HTML généré" in result.output
        assert html_path.exists()

        # Read and validate HTML structure
        html_content = html_path.read_text()

        # DOCTYPE and basic HTML structure
        assert "<!DOCTYPE html>" in html_content
        assert "<html lang=\"fr\">" in html_content
        assert "</html>" in html_content

        # Head section
        assert "<head>" in html_content
        assert "<meta charset=\"UTF-8\">" in html_content
        assert "<meta name=\"viewport\"" in html_content
        assert "<title>City Compare" in html_content
        assert "</head>" in html_content

        # Chart.js inclusion
        assert "chart.js" in html_content.lower()

        # CSS styles
        assert "<style>" in html_content
        assert ":root {" in html_content
        assert "--primary:" in html_content
        assert "</style>" in html_content

        # Body structure
        assert "<body>" in html_content
        assert "</body>" in html_content

        # Container and card elements
        assert "container" in html_content
        assert "card" in html_content

        # City names in content
        assert "Marseille" in html_content
        assert "Nice" in html_content
        assert "Montpellier" in html_content

        # Ranking section
        assert "ranking" in html_content.lower() or "Classement" in html_content

        # Table structure
        assert "<table>" in html_content
        assert "<thead>" in html_content
        assert "<tbody>" in html_content
        assert "</table>" in html_content

        # Table headers (metrics)
        assert "Loyer" in html_content
        assert "Temp" in html_content
        assert "Score" in html_content

        # Chart canvases
        assert "barChart" in html_content
        assert "radarChart" in html_content
        assert "weatherChart" in html_content

        # Chart.js initialization scripts
        assert "<script>" in html_content
        assert "new Chart(" in html_content
        assert "type: 'bar'" in html_content
        assert "type: 'radar'" in html_content

        # Footer
        assert "footer" in html_content.lower()
        assert "City Compare" in html_content

        # Configuration info
        assert "Configuration" in html_content or "Profil" in html_content


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 11: Generate all outputs at once
# ═══════════════════════════════════════════════════════════════════


class TestExample11AllOutputs:
    """Example 11: city-compare compare "Lyon" "Lille" "Nantes" -o report.md --json summary.json --html rapport.html"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_all_outputs_generation(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test generating all output formats at once."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        md_path = temp_dir / "report.md"
        json_path = temp_dir / "summary.json"
        html_path = temp_dir / "rapport.html"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lyon",
                "Lille",
                "Nantes",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "-o", str(md_path),
                "--json", str(json_path),
                "--html", str(html_path),
            ],
        )

        assert result.exit_code == 0

        # Verify all output confirmations
        assert "Rapport généré" in result.output
        assert "JSON généré" in result.output
        assert "HTML généré" in result.output

        # Verify all files exist
        assert md_path.exists()
        assert json_path.exists()
        assert html_path.exists()

        # Verify content consistency across formats
        md_content = md_path.read_text()
        html_content = html_path.read_text()
        with open(json_path) as f:
            json_data = json.load(f)

        # All cities appear in all formats
        for city in ["Lyon", "Lille", "Nantes"]:
            assert city in md_content
            assert city in html_content
            assert city in json_data["cities"]


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 12: Include detailed scoring explanation
# ═══════════════════════════════════════════════════════════════════


class TestExample12ExplainOption:
    """Example 12: city-compare compare "Paris" "Lyon" --explain"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_explain_option(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test --explain flag includes detailed scoring explanation."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Paris",
                "Lyon",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
                "--explain",
            ],
        )

        assert result.exit_code == 0
        assert output_path.exists()

        # Report should contain explanation details
        report = output_path.read_text()
        
        # Should have variable explanations
        assert "rent_m2" in report or "Variables" in report
        
        # Should have scoring details (bonus/penalty)
        assert "bonus" in report.lower() or "score" in report.lower()


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 13: Include air quality data in comparison
# ═══════════════════════════════════════════════════════════════════


class TestExample13AirQuality:
    """Example 13: city-compare compare "Lyon" "Marseille" --air-quality"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    @patch("city_compare.cli.OpenMeteoAirQualityClient")
    def test_air_quality_option(
        self,
        mock_air_class: MagicMock,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test --air-quality flag includes air quality data."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()
        mock_air_class.return_value = create_mock_air_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Lyon",
                "Marseille",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
                "--air-quality",
            ],
        )

        assert result.exit_code == 0

        # Verify air quality client was used
        mock_air_class.assert_called_once()
        air_client = mock_air_class.return_value
        assert air_client.get_air_quality.call_count == 2  # Called for both cities


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 14: Full analysis with explanation and air quality
# ═══════════════════════════════════════════════════════════════════


class TestExample14FullAnalysis:
    """Example 14: city-compare compare "Bordeaux" "Toulouse" "Montpellier" -e -a --html full_report.html"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    @patch("city_compare.cli.OpenMeteoAirQualityClient")
    def test_full_analysis_with_all_options(
        self,
        mock_air_class: MagicMock,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test full analysis with -e (explain) and -a (air quality) short flags."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()
        mock_air_class.return_value = create_mock_air_client()

        output_path = temp_dir / "report.md"
        html_path = temp_dir / "full_report.html"

        result = runner.invoke(
            app,
            [
                "compare",
                "Bordeaux",
                "Toulouse",
                "Montpellier",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
                "-e",  # Short flag for --explain
                "-a",  # Short flag for --air-quality
                "--html", str(html_path),
            ],
        )

        assert result.exit_code == 0
        assert html_path.exists()

        # Verify air quality was used
        mock_air_class.assert_called_once()
        assert mock_air_class.return_value.get_air_quality.call_count == 3  # 3 cities

        # Verify explanation is in report
        report = output_path.read_text()
        assert "rent_m2" in report or "Variables" in report or "bonus" in report.lower()


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 15: Disable SSL verification
# ═══════════════════════════════════════════════════════════════════


class TestExample15NoVerifySSL:
    """Example 15: city-compare compare "Rennes" "Brest" --no-verify-ssl"""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_no_verify_ssl_option(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        """Test --no-verify-ssl flag passes verify_ssl=False to clients."""
        mock_geocoder_class.return_value = create_mock_geocoder()
        mock_weather_class.return_value = create_mock_weather_client()

        output_path = temp_dir / "report.md"

        result = runner.invoke(
            app,
            [
                "compare",
                "Rennes",
                "Brest",
                "--profile", str(mock_profile),
                "--rules", str(mock_rules),
                "--out", str(output_path),
                "--no-verify-ssl",
            ],
        )

        assert result.exit_code == 0

        # Verify clients were initialized with verify_ssl=False
        geocoder_call_kwargs = mock_geocoder_class.call_args
        weather_call_kwargs = mock_weather_class.call_args

        # Check verify_ssl was passed as False
        assert geocoder_call_kwargs[1].get("verify_ssl") is False
        assert weather_call_kwargs[1].get("verify_ssl") is False


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 16: Clear all cached data
# ═══════════════════════════════════════════════════════════════════


class TestExample16ClearCache:
    """Example 16: city-compare clear-cache"""

    def test_clear_cache_command(self):
        """Test clear-cache command output."""
        result = runner.invoke(app, ["clear-cache"])

        assert result.exit_code == 0
        assert "Cache vidé" in result.output


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 17: View recent comparison history
# ═══════════════════════════════════════════════════════════════════


class TestExample17HistoryList:
    """Example 17: city-compare history"""

    def test_history_empty(self, temp_dir: Path):
        """Test history command with empty history."""
        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            mock_history = MagicMock()
            mock_history.search.return_value = []
            mock_history_class.return_value = mock_history

            result = runner.invoke(app, ["history"])

            assert result.exit_code == 0
            assert "Aucun historique trouvé" in result.output

    def test_history_with_entries(self, temp_dir: Path):
        """Test history command with existing entries."""
        from datetime import datetime

        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            # Create mock history entries
            mock_entry = MagicMock()
            mock_entry.id = 1
            mock_entry.timestamp = "2026-01-05 10:30:00"
            mock_entry.cities = ["Lyon", "Nantes"]
            mock_entry.winner = "Lyon"
            mock_entry.scores = {"Lyon": 15.0, "Nantes": 12.0}

            mock_history = MagicMock()
            mock_history.search.return_value = [mock_entry]
            mock_history_class.return_value = mock_history

            result = runner.invoke(app, ["history"])

            assert result.exit_code == 0
            assert "Historique des comparaisons" in result.output
            assert "Lyon" in result.output
            assert "Nantes" in result.output


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 18: Filter history by city and limit results
# ═══════════════════════════════════════════════════════════════════


class TestExample18HistoryFilter:
    """Example 18: city-compare history --city "Lyon" --limit 10"""

    def test_history_filter_by_city(self):
        """Test history filtering by city name."""
        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            mock_entry = MagicMock()
            mock_entry.id = 1
            mock_entry.timestamp = "2026-01-05 10:30:00"
            mock_entry.cities = ["Lyon", "Paris"]
            mock_entry.winner = "Lyon"

            mock_history = MagicMock()
            mock_history.search.return_value = [mock_entry]
            mock_history_class.return_value = mock_history

            result = runner.invoke(app, ["history", "--city", "Lyon", "--limit", "10"])

            assert result.exit_code == 0
            
            # Verify search was called with correct filters
            mock_history.search.assert_called_once_with(city="Lyon", winner=None, limit=10)

    def test_history_filter_by_winner(self):
        """Test history filtering by winner."""
        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            mock_entry = MagicMock()
            mock_entry.id = 2
            mock_entry.timestamp = "2026-01-05 11:00:00"
            mock_entry.cities = ["Lyon", "Marseille"]
            mock_entry.winner = "Marseille"

            mock_history = MagicMock()
            mock_history.search.return_value = [mock_entry]
            mock_history_class.return_value = mock_history

            result = runner.invoke(app, ["history", "--winner", "Marseille"])

            assert result.exit_code == 0
            mock_history.search.assert_called_once_with(city=None, winner="Marseille", limit=20)


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 19: Show statistics and export history
# ═══════════════════════════════════════════════════════════════════


class TestExample19HistoryStats:
    """Example 19: city-compare history --stats / city-compare history --export historique.json"""

    def test_history_stats(self):
        """Test history --stats command."""
        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            mock_history = MagicMock()
            mock_history.get_stats.return_value = {
                "total_comparisons": 15,
                "comparisons_last_7_days": 5,
                "top_winners": {"Lyon": 8, "Paris": 4, "Nantes": 3},
                "most_compared_cities": {"Lyon": 12, "Paris": 10, "Marseille": 8},
            }
            mock_history_class.return_value = mock_history

            result = runner.invoke(app, ["history", "--stats"])

            assert result.exit_code == 0
            assert "Statistiques historique" in result.output
            assert "Total comparaisons: 15" in result.output
            assert "7 derniers jours" in result.output
            assert "Top gagnants" in result.output
            assert "Lyon" in result.output
            assert "Villes les plus comparées" in result.output

    def test_history_stats_empty(self):
        """Test history --stats with no data."""
        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            mock_history = MagicMock()
            mock_history.get_stats.return_value = {
                "total_comparisons": 0,
                "comparisons_last_7_days": 0,
                "top_winners": {},
                "most_compared_cities": {},
            }
            mock_history_class.return_value = mock_history

            result = runner.invoke(app, ["history", "--stats"])

            assert result.exit_code == 0
            assert "Total comparaisons: 0" in result.output

    def test_history_export(self, temp_dir: Path):
        """Test history --export command."""
        export_path = temp_dir / "historique.json"

        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            mock_history = MagicMock()
            mock_history.export_json.return_value = '{"entries": []}'
            mock_history_class.return_value = mock_history

            result = runner.invoke(app, ["history", "--export", str(export_path)])

            assert result.exit_code == 0
            assert "exporté" in result.output
            assert export_path.exists()


# ═══════════════════════════════════════════════════════════════════
#  EXAMPLE 20: Show specific entry details by ID
# ═══════════════════════════════════════════════════════════════════


class TestExample20HistoryShowEntry:
    """Example 20: city-compare history --show 5"""

    def test_history_show_existing_entry(self):
        """Test history --show with existing entry."""
        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            mock_entry = MagicMock()
            mock_entry.id = 5
            mock_entry.timestamp = "2026-01-05 14:30:00"
            mock_entry.cities = ["Lyon", "Bordeaux", "Nantes"]
            mock_entry.winner = "Lyon"
            mock_entry.scores = {"Lyon": 18.5, "Bordeaux": 15.0, "Nantes": 14.2}

            mock_history = MagicMock()
            mock_history.get.return_value = mock_entry
            mock_history_class.return_value = mock_history

            result = runner.invoke(app, ["history", "--show", "5"])

            assert result.exit_code == 0
            assert "Comparison #5" in result.output
            assert "Lyon" in result.output
            assert "Bordeaux" in result.output
            assert "Nantes" in result.output
            assert "Winner" in result.output or "winner" in result.output.lower()

    def test_history_show_nonexistent_entry(self):
        """Test history --show with non-existent entry."""
        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            mock_history = MagicMock()
            mock_history.get.return_value = None
            mock_history_class.return_value = mock_history

            result = runner.invoke(app, ["history", "--show", "999"])

            assert result.exit_code == 1
            assert "not found" in result.output


# ═══════════════════════════════════════════════════════════════════
#  ADDITIONAL: Version flag test
# ═══════════════════════════════════════════════════════════════════


class TestVersionFlag:
    """Test --version flag."""

    def test_version_output(self):
        """Test city-compare --version output."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "city-compare" in result.output.lower()
        assert "version" in result.output.lower()
        # Version should match semver pattern
        assert re.search(r"\d+\.\d+\.\d+", result.output)


# ═══════════════════════════════════════════════════════════════════
#  ADDITIONAL: Config command tests
# ═══════════════════════════════════════════════════════════════════


class TestConfigCommand:
    """Test config command."""

    def test_config_show(self):
        """Test city-compare config --show output."""
        result = runner.invoke(app, ["config", "--show"])

        assert result.exit_code == 0
        
        # Should output configuration directories info
        assert "Config" in result.output or "Configuration" in result.output
        assert "Data" in result.output or "Cache" in result.output

    def test_config_init(self, temp_dir: Path):
        """Test city-compare config --init."""
        with patch("city_compare.xdg.init_config") as mock_init:
            mock_init.return_value = {
                "profile": temp_dir / "profile.yml",
                "rules": temp_dir / "rules.rules",
            }

            result = runner.invoke(app, ["config", "--init"])

            assert result.exit_code == 0
            mock_init.assert_called_once()

    def test_config_copy_local(self):
        """Test city-compare config --copy-local."""
        with patch("city_compare.xdg.copy_local_config_to_xdg") as mock_copy:
            mock_copy.return_value = {}

            result = runner.invoke(app, ["config", "--copy-local"])

            assert result.exit_code == 0
            mock_copy.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
#  ADDITIONAL: Completion script tests
# ═══════════════════════════════════════════════════════════════════


class TestCompletionCommand:
    """Test shell completion commands."""

    def test_bash_completion(self):
        """Test city-compare completion bash generates valid bash script."""
        result = runner.invoke(app, ["completion", "bash"])

        assert result.exit_code == 0
        
        # Valid bash completion script structure
        assert "_city_compare_completions" in result.output or "complete" in result.output
        assert "COMP" in result.output  # Bash completion variables
        assert "compgen" in result.output or "COMPREPLY" in result.output

    def test_zsh_completion(self):
        """Test city-compare completion zsh generates valid zsh script."""
        result = runner.invoke(app, ["completion", "zsh"])

        assert result.exit_code == 0
        
        # Valid zsh completion script structure
        assert "#compdef" in result.output or "compadd" in result.output or "_city" in result.output

    def test_fish_completion(self):
        """Test city-compare completion fish generates valid fish script."""
        result = runner.invoke(app, ["completion", "fish"])

        assert result.exit_code == 0
        
        # Valid fish completion script structure
        assert "complete" in result.output
        assert "city-compare" in result.output

    def test_invalid_shell_completion(self):
        """Test completion with invalid shell type."""
        result = runner.invoke(app, ["completion", "invalid_shell"])

        assert result.exit_code == 1


# ═══════════════════════════════════════════════════════════════════
#  ADDITIONAL: Error handling tests
# ═══════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Test error handling for various scenarios."""

    def test_single_city_error(self):
        """Test error when only one city is provided."""
        result = runner.invoke(app, ["compare", "Lyon"])

        assert result.exit_code == 1
        assert "2 villes" in result.output

    def test_missing_profile_error(self, temp_dir: Path):
        """Test error when profile file doesn't exist."""
        result = runner.invoke(
            app,
            [
                "compare",
                "Lyon",
                "Nantes",
                "--profile", str(temp_dir / "nonexistent.yml"),
            ],
        )

        assert result.exit_code == 1
        assert "introuvable" in result.output.lower()

    def test_history_clear_confirmation(self):
        """Test history --clear asks for confirmation."""
        with patch("city_compare.history.ComparisonHistory") as mock_history_class:
            mock_history = MagicMock()
            mock_history_class.return_value = mock_history

            # Simulate user saying "no" to confirmation
            result = runner.invoke(app, ["history", "--clear"], input="n\n")

            assert result.exit_code == 0
            # Clear should not have been called
            mock_history.clear.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
#  ADDITIONAL: API Server test
# ═══════════════════════════════════════════════════════════════════


class TestServeCommand:
    """Test serve command (API server)."""

    def test_serve_starts_and_responds(self):
        """Test that the API server app works correctly using TestClient."""
        from fastapi.testclient import TestClient
        from city_compare.api import app

        # Use FastAPI's TestClient to test without network
        with TestClient(app) as client:
            # Test health endpoint
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data

            # Test docs endpoint exists
            response = client.get("/docs")
            assert response.status_code == 200

            # Test OpenAPI schema
            response = client.get("/openapi.json")
            assert response.status_code == 200
            schema = response.json()
            assert "paths" in schema
            assert "/health" in schema["paths"]
            assert "/compare" in schema["paths"]
            assert "/cities" in schema["paths"]

    def test_api_cities_endpoint(self):
        """Test the /cities endpoint."""
        from fastapi.testclient import TestClient
        from city_compare.api import app

        with patch("city_compare.api.ProfileConfig") as mock_config_class, \
             patch("city_compare.api.RentDataParser") as mock_parser_class:
            # Mock the config and parser
            mock_config = MagicMock()
            mock_config.rent_csv_path = "fake.csv"
            mock_config_class.from_yaml.return_value = mock_config

            mock_parser = MagicMock()
            mock_parser.list_cities.return_value = ["Lyon", "Paris", "Marseille"]
            mock_parser_class.return_value = mock_parser

            with TestClient(app) as client:
                response = client.get("/cities")
                assert response.status_code == 200
                data = response.json()
                assert "cities" in data
                assert "total" in data
                assert isinstance(data["cities"], list)
                assert len(data["cities"]) == 3
