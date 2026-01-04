"""Command-line interface for city-compare."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import __version__
from .cache import LocalCache
from .geocoding import GeocodingError, NominatimGeocoder
from .models import (
    CityMetrics,
    ComparisonResult,
    ProfileConfig,
    ScoringResult,
)
from .rent import RentDataError, RentDataParser
from .report import (
    generate_json_summary,
    generate_markdown_report,
    save_json,
    save_report,
)
from .scoring import ScoringDSL, ScoringError
from .weather import OpenMeteoClient, WeatherError

app = typer.Typer(
    name="city-compare",
    help="Compare French cities and generate reports with explainable scores.",
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"city-compare version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """City Compare - Compare French cities."""
    pass


@app.command()
def compare(
    city_a: Annotated[str, typer.Argument(help="First city name")],
    city_b: Annotated[str, typer.Argument(help="Second city name")],
    profile: Annotated[
        Path,
        typer.Option("--profile", "-p", help="Path to profile YAML file"),
    ] = Path("profiles/default.yml"),
    rules: Annotated[
        Path,
        typer.Option("--rules", "-r", help="Path to scoring rules file"),
    ] = Path("profiles/default.rules"),
    out: Annotated[
        Path,
        typer.Option("--out", "-o", help="Output path for report"),
    ] = Path("report.md"),
    explain: Annotated[
        bool,
        typer.Option("--explain", "-e", help="Include detailed scoring explanation"),
    ] = False,
    json_out: Annotated[
        Optional[Path],
        typer.Option("--json", "-j", help="Output path for JSON summary"),
    ] = None,
    no_verify_ssl: Annotated[
        bool,
        typer.Option("--no-verify-ssl", help="Disable SSL certificate verification"),
    ] = False,
) -> None:
    """
    Compare two French cities and generate a report.

    Example:
        city-compare compare "Lille" "Nantes" --profile profiles/default.yml --out report.md
    """
    verify_ssl = not no_verify_ssl
    
    try:
        # Load configuration
        console.print(f"\n[bold blue]🏙️  Comparaison: {city_a} vs {city_b}[/bold blue]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Load profile
            task = progress.add_task("Chargement du profil...", total=None)
            try:
                config = ProfileConfig.from_yaml(profile)
            except FileNotFoundError:
                console.print(f"[red]❌ Profil introuvable: {profile}[/red]")
                raise typer.Exit(1)
            progress.update(task, completed=True)

            # Load scoring rules
            task = progress.add_task("Chargement des règles de scoring...", total=None)
            try:
                dsl = ScoringDSL(rules_path=rules)
            except ScoringError as e:
                console.print(f"[red]❌ Erreur dans les règles: {e}[/red]")
                raise typer.Exit(1)
            progress.update(task, completed=True)

            # Initialize services
            cache = LocalCache()
            geocoder = NominatimGeocoder(cache, verify_ssl=verify_ssl)
            weather_client = OpenMeteoClient(cache, verify_ssl=verify_ssl)
            rent_parser = RentDataParser(config.rent_csv_path)

            # Process city A
            task = progress.add_task(f"Traitement de {city_a}...", total=None)
            metrics_a = _process_city(city_a, geocoder, weather_client, rent_parser, config)
            progress.update(task, completed=True)

            # Process city B
            task = progress.add_task(f"Traitement de {city_b}...", total=None)
            metrics_b = _process_city(city_b, geocoder, weather_client, rent_parser, config)
            progress.update(task, completed=True)

            # Calculate scores
            task = progress.add_task("Calcul des scores...", total=None)
            score_a_value, vars_a = dsl.evaluate(
                metrics_a.rent.rent_m2,
                metrics_a.weather.avg_temp_c,
                metrics_a.weather.rain_days,
                metrics_a.weather.hot_days,
            )
            score_b_value, vars_b = dsl.evaluate(
                metrics_b.rent.rent_m2,
                metrics_b.weather.avg_temp_c,
                metrics_b.weather.rain_days,
                metrics_b.weather.hot_days,
            )
            progress.update(task, completed=True)

        # Build results
        score_a = ScoringResult(city_name=city_a, score=score_a_value, variables=vars_a)
        score_b = ScoringResult(city_name=city_b, score=score_b_value, variables=vars_b)

        if score_a_value > score_b_value:
            winner = city_a
        elif score_b_value > score_a_value:
            winner = city_b
        else:
            winner = "Égalité"

        result = ComparisonResult(
            city_a=metrics_a,
            city_b=metrics_b,
            score_a=score_a,
            score_b=score_b,
            winner=winner,
            profile_used=str(profile),
            rules_used=str(rules),
        )

        # Generate report
        explanation_a = dsl.get_explanation(vars_a) if explain else ""
        explanation_b = dsl.get_explanation(vars_b) if explain else ""

        report = generate_markdown_report(
            result,
            explain=explain,
            dsl_explanation_a=explanation_a,
            dsl_explanation_b=explanation_b,
        )
        save_report(report, out)
        console.print(f"[green]✅ Rapport généré: {out}[/green]")

        # Generate JSON if requested
        if json_out:
            summary = generate_json_summary(result, vars_a, vars_b)
            save_json(summary, json_out)
            console.print(f"[green]✅ JSON généré: {json_out}[/green]")

        # Print summary
        console.print()
        console.print(f"[bold]Résultat:[/bold]")
        console.print(f"  {city_a}: [cyan]{score_a_value:.2f}[/cyan]")
        console.print(f"  {city_b}: [cyan]{score_b_value:.2f}[/cyan]")
        console.print(f"  [bold green]🏆 Gagnant: {winner}[/bold green]")
        console.print()

    except (GeocodingError, WeatherError, RentDataError, ScoringError) as e:
        console.print(f"[red]❌ Erreur: {e}[/red]")
        raise typer.Exit(1)


def _process_city(
    city_name: str,
    geocoder: NominatimGeocoder,
    weather_client: OpenMeteoClient,
    rent_parser: RentDataParser,
    config: ProfileConfig,
) -> CityMetrics:
    """Process a single city and gather all metrics."""
    geo = geocoder.geocode(city_name)
    weather = weather_client.get_weather(geo, config)
    rent = rent_parser.get_rent(city_name)

    return CityMetrics(
        city_name=city_name,
        geo=geo,
        weather=weather,
        rent=rent,
    )


@app.command()
def clear_cache() -> None:
    """Clear the local cache (geocoding and weather data)."""
    cache = LocalCache()
    cache.clear()
    console.print("[green]✅ Cache vidé[/green]")


if __name__ == "__main__":
    app()
