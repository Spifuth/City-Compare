"""An upstream outage must not look like a bug in this program.

The job that generated the example report failed on 2026-09-09 because
Open-Meteo returned a 502. Nothing in the code was wrong, and nothing in the
exit status said so: a third-party outage and a malformed rules file both left
the CLI with exit code 1.

These tests pin the distinction, in both directions — the second half matters
more than the first, because the tempting fix (treat every HTTP error as an
outage) would bury a genuine 400 caused by parameters this package builds
itself.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from city_compare.air_quality import AirQualityError, AirQualityUnavailable
from city_compare.cli import app
from city_compare.geocoding import GeocodingError, GeocodingUnavailable
from city_compare.upstream import EX_TEMPFAIL, UpstreamUnavailable, is_transient
from city_compare.weather import WeatherError, WeatherUnavailable

from .test_cli_examples import create_mock_geocoder

runner = CliRunner()


# Local fixtures rather than imports from test_cli_examples: importing a
# pytest fixture rebinds the name at module scope, which ruff flags as F811 and
# which quietly shadows the real fixture if the two ever drift. These are three
# lines of setup; sharing them is not worth the coupling.


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_profile(temp_dir: Path) -> Path:
    rent_csv = temp_dir / "loyers.csv"
    rent_csv.write_text("commune,loyer_med,departement\nLyon,14.2,69\nBordeaux,13.0,33\n")
    profile = temp_dir / "default.yml"
    profile.write_text(
        f"rain_threshold_mm: 1.0\nhot_threshold_c: 30.0\n"
        f'weather_months: 12\nrent_csv_path: "{rent_csv}"\n'
    )
    return profile


@pytest.fixture
def mock_rules(temp_dir: Path) -> Path:
    rules = temp_dir / "default.rules"
    rules.write_text("rent_m2 < 10 => bonus(15)\navg_temp >= 12 and avg_temp <= 18 => bonus(5)\n")
    return rules


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.invalid/")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(f"{code}", request=request, response=response)


class TestIsTransient:
    @pytest.mark.parametrize("code", [500, 502, 503, 504, 429])
    def test_server_errors_and_rate_limiting_are_transient(self, code: int):
        assert is_transient(_status_error(code)) is True

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
    def test_client_errors_are_not_transient(self, code: int):
        # A 400 is this package building bad parameters. Retrying gets the same
        # 400, and calling it an outage hides the bug.
        assert is_transient(_status_error(code)) is False

    def test_timeouts_and_refused_connections_are_transient(self):
        request = httpx.Request("GET", "https://example.invalid/")
        assert is_transient(httpx.ConnectTimeout("timed out", request=request)) is True
        assert is_transient(httpx.ConnectError("refused", request=request)) is True

    def test_an_unrelated_exception_is_not_transient(self):
        assert is_transient(ValueError("nothing to do with the network")) is False


class TestErrorHierarchy:
    """The transient types must stay catchable by the existing handlers."""

    @pytest.mark.parametrize(
        ("transient", "base"),
        [
            (WeatherUnavailable, WeatherError),
            (GeocodingUnavailable, GeocodingError),
            (AirQualityUnavailable, AirQualityError),
        ],
    )
    def test_transient_errors_are_still_their_service_error(self, transient, base):
        # cli.py catches (GeocodingError, WeatherError, ...). If the new types
        # fell outside that tuple, an outage would escape as a traceback.
        assert issubclass(transient, base)
        assert issubclass(transient, UpstreamUnavailable)


class TestExitCode:
    def test_ex_tempfail_is_the_sysexits_value(self):
        # Hard-coded on purpose: the CI step greps for this number, so it is a
        # published interface, not an implementation detail.
        assert EX_TEMPFAIL == 75


class TestCliExitCode:
    """The contract the CI step depends on, exercised through the real CLI."""

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_a_502_from_the_weather_api_exits_75_not_1(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        mock_geocoder_class.return_value = create_mock_geocoder()
        weather = MagicMock()
        weather.get_weather.side_effect = WeatherUnavailable(
            "HTTP error fetching weather data: Server error '502 Bad Gateway'"
        )
        mock_weather_class.return_value = weather

        result = runner.invoke(
            app,
            [
                "compare",
                "Lyon",
                "Bordeaux",
                "--profile",
                str(mock_profile),
                "--rules",
                str(mock_rules),
                "--out",
                str(temp_dir / "report.md"),
            ],
        )

        assert result.exit_code == EX_TEMPFAIL, result.output
        assert "Service externe indisponible" in result.output

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_a_real_failure_still_exits_1(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        # The half of the change that is easy to get wrong: if every failure
        # became EX_TEMPFAIL, CI would go green on a genuine bug.
        mock_geocoder_class.return_value = create_mock_geocoder()
        weather = MagicMock()
        weather.get_weather.side_effect = WeatherError("No temperature data available")
        mock_weather_class.return_value = weather

        result = runner.invoke(
            app,
            [
                "compare",
                "Lyon",
                "Bordeaux",
                "--profile",
                str(mock_profile),
                "--rules",
                str(mock_rules),
                "--out",
                str(temp_dir / "report.md"),
            ],
        )

        assert result.exit_code == 1, result.output

    @patch("city_compare.cli.NominatimGeocoder")
    @patch("city_compare.cli.OpenMeteoClient")
    def test_no_partial_report_is_written_on_an_outage(
        self,
        mock_weather_class: MagicMock,
        mock_geocoder_class: MagicMock,
        temp_dir: Path,
        mock_profile: Path,
        mock_rules: Path,
    ):
        # Weather is a scored dimension. A report generated without it is not a
        # comparison with a gap, it is a different ranking under the same
        # heading — so nothing must be written at all.
        mock_geocoder_class.return_value = create_mock_geocoder()
        weather = MagicMock()
        weather.get_weather.side_effect = WeatherUnavailable("502")
        mock_weather_class.return_value = weather
        out = temp_dir / "report.md"

        runner.invoke(
            app,
            [
                "compare",
                "Lyon",
                "Bordeaux",
                "--profile",
                str(mock_profile),
                "--rules",
                str(mock_rules),
                "--out",
                str(out),
            ],
        )

        assert not out.exists()
