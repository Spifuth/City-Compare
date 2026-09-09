"""Command-line interface for city-compare."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import __version__
from .air_quality import AirQualityError, OpenMeteoAirQualityClient
from .cache import LocalCache
from .geocoding import GeocodingError, NominatimGeocoder
from .html_report import generate_html_report, generate_html_report_two_cities, save_html_report
from .models import (
    AirQualityData,
    CityMetrics,
    ComparisonResult,
    MultiComparisonResult,
    ProfileConfig,
    ScoringResult,
)
from .rent import RentDataError, RentDataParser
from .report import (
    generate_json_summary,
    generate_markdown_report,
    generate_multi_json_summary,
    generate_multi_markdown_report,
    save_json,
    save_report,
)
from .scoring import ScoringDSL, ScoringError
from .upstream import EX_TEMPFAIL, UpstreamUnavailable
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
        bool | None,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """City Compare - Compare French cities."""
    pass


@app.command()
def compare(
    cities: Annotated[
        list[str],
        typer.Argument(help="Cities to compare (2 or more)"),
    ],
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
        Path | None,
        typer.Option("--json", "-j", help="Output path for JSON summary"),
    ] = None,
    air_quality: Annotated[
        bool,
        typer.Option("--air-quality", "-a", help="Include air quality data"),
    ] = False,
    html_out: Annotated[
        Path | None,
        typer.Option("--html", help="Output path for HTML report with charts"),
    ] = None,
    no_verify_ssl: Annotated[
        bool,
        typer.Option("--no-verify-ssl", help="Disable SSL certificate verification"),
    ] = False,
) -> None:
    """
    Compare French cities and generate a report.

    Examples:
        city-compare compare "Lille" "Nantes"
        city-compare compare "Lyon" "Bordeaux" "Toulouse" "Marseille"
    """
    if len(cities) < 2:
        console.print("[red]❌ Au moins 2 villes sont requises pour la comparaison[/red]")
        raise typer.Exit(1)

    verify_ssl = not no_verify_ssl

    try:
        # Display header
        cities_str = " vs ".join(cities)
        console.print(f"\n[bold blue]🏙️  Comparaison: {cities_str}[/bold blue]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Load profile
            task = progress.add_task("Chargement du profil...", total=None)
            try:
                config = ProfileConfig.from_yaml(profile)
            except FileNotFoundError as err:
                console.print(f"[red]❌ Profil introuvable: {profile}[/red]")
                raise typer.Exit(1) from err
            progress.update(task, completed=True)

            # Load scoring rules
            task = progress.add_task("Chargement des règles de scoring...", total=None)
            try:
                dsl = ScoringDSL(rules_path=rules)
            except ScoringError as e:
                console.print(f"[red]❌ Erreur dans les règles: {e}[/red]")
                raise typer.Exit(1) from e
            progress.update(task, completed=True)

            # Initialize services
            cache = LocalCache()
            geocoder = NominatimGeocoder(cache, verify_ssl=verify_ssl)
            weather_client = OpenMeteoClient(cache, verify_ssl=verify_ssl)
            rent_parser = RentDataParser(config.rent_csv_path)
            air_client = (
                OpenMeteoAirQualityClient(cache, verify_ssl=verify_ssl) if air_quality else None
            )

            # Process all cities
            all_metrics: list[CityMetrics] = []
            for city in cities:
                task = progress.add_task(f"Traitement de {city}...", total=None)
                metrics = _process_city(
                    city, geocoder, weather_client, rent_parser, config, air_client
                )
                all_metrics.append(metrics)
                progress.update(task, completed=True)

            # Calculate scores for all cities
            task = progress.add_task("Calcul des scores...", total=None)
            all_scores: list[ScoringResult] = []
            all_vars: list[dict[str, float]] = []

            for metrics in all_metrics:
                score_value, variables = dsl.evaluate(
                    metrics.rent.rent_m2,
                    metrics.weather.avg_temp_c,
                    metrics.weather.rain_days,
                    metrics.weather.hot_days,
                )
                all_vars.append(variables)
                all_scores.append(
                    ScoringResult(
                        city_name=metrics.city_name,
                        score=score_value,
                        variables=variables,
                    )
                )
            progress.update(task, completed=True)

        # Sort by score descending and assign ranks
        sorted_scores = sorted(all_scores, key=lambda s: s.score, reverse=True)
        for i, score in enumerate(sorted_scores):
            score.rank = i + 1

        ranking = [s.city_name for s in sorted_scores]
        winner = ranking[0]

        # Generate report based on number of cities
        if len(cities) == 2:
            # Legacy 2-city comparison
            result = ComparisonResult(
                city_a=all_metrics[0],
                city_b=all_metrics[1],
                score_a=all_scores[0],
                score_b=all_scores[1],
                winner=winner,
                profile_used=str(profile),
                rules_used=str(rules),
            )

            explanation_a = dsl.get_explanation(all_vars[0]) if explain else ""
            explanation_b = dsl.get_explanation(all_vars[1]) if explain else ""

            report = generate_markdown_report(
                result,
                explain=explain,
                dsl_explanation_a=explanation_a,
                dsl_explanation_b=explanation_b,
            )

            if json_out:
                summary = generate_json_summary(result, all_vars[0], all_vars[1])
                save_json(summary, json_out)

            if html_out:
                html = generate_html_report_two_cities(result)
                save_html_report(html, html_out)
        else:
            # Multi-city comparison
            result_multi = MultiComparisonResult(
                cities=all_metrics,
                scores=sorted_scores,
                ranking=ranking,
                profile_used=str(profile),
                rules_used=str(rules),
            )

            explanations = {}
            if explain:
                for score in sorted_scores:
                    explanations[score.city_name] = dsl.get_explanation(score.variables)

            report = generate_multi_markdown_report(result_multi, explain, explanations)

            if json_out:
                summary = generate_multi_json_summary(result_multi)
                save_json(summary, json_out)

            if html_out:
                html = generate_html_report(result_multi)
                save_html_report(html, html_out)

        save_report(report, out)
        console.print(f"[green]✅ Rapport généré: {out}[/green]")

        if json_out:
            console.print(f"[green]✅ JSON généré: {json_out}[/green]")

        if html_out:
            console.print(f"[green]✅ HTML généré: {html_out}[/green]")

        # Print summary
        console.print()
        console.print("[bold]Classement:[/bold]")
        for i, score in enumerate(sorted_scores):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i + 1}."
            console.print(f"  {medal} {score.city_name}: [cyan]{score.score:.2f}[/cyan]")
        console.print()

    # Ordered on purpose: UpstreamUnavailable is a subclass of the service
    # errors below, so it has to be caught first or it never matches.
    except UpstreamUnavailable as e:
        console.print(f"[yellow]⚠️  Service externe indisponible: {e}[/yellow]")
        console.print(
            "[dim]Ce n'est pas une erreur de city-compare. Réessaie plus tard ; "
            f"le code de sortie {EX_TEMPFAIL} (EX_TEMPFAIL) le signale aux scripts "
            "et à la CI.[/dim]"
        )
        # Deliberately not a partial report. Weather and air quality are scored
        # dimensions: dropping one silently does not produce a comparison with
        # a hole in it, it produces a DIFFERENT ranking wearing the same
        # heading. Failing loudly is the honest outcome; the exit code is what
        # says whose fault it was.
        raise typer.Exit(EX_TEMPFAIL) from e
    except (GeocodingError, WeatherError, RentDataError, ScoringError, AirQualityError) as e:
        console.print(f"[red]❌ Erreur: {e}[/red]")
        raise typer.Exit(1) from e


def _process_city(
    city_name: str,
    geocoder: NominatimGeocoder,
    weather_client: OpenMeteoClient,
    rent_parser: RentDataParser,
    config: ProfileConfig,
    air_client: OpenMeteoAirQualityClient | None = None,
) -> CityMetrics:
    """Process a single city and gather all metrics."""
    geo = geocoder.geocode(city_name)
    weather = weather_client.get_weather(geo, config)
    rent = rent_parser.get_rent(city_name)

    # Fetch air quality if client provided
    air_data = None
    if air_client:
        aq = air_client.get_air_quality(geo)
        air_data = AirQualityData(
            aqi_avg=aq.aqi_avg,
            pm2_5_avg=aq.pm2_5_avg,
            pm10_avg=aq.pm10_avg,
            good_days=aq.good_days,
            moderate_days=aq.moderate_days,
            unhealthy_days=aq.unhealthy_days,
            quality_label=aq.quality_label,
        )

    return CityMetrics(
        city_name=city_name,
        geo=geo,
        weather=weather,
        rent=rent,
        air_quality=air_data,
    )


@app.command()
def clear_cache() -> None:
    """Clear the local cache (geocoding and weather data)."""
    cache = LocalCache()
    cache.clear()
    console.print("[green]✅ Cache vidé[/green]")


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-P", help="Port to bind to"),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option("--reload", help="Enable auto-reload for development"),
    ] = False,
) -> None:
    """
    Start the REST API server.

    Runs a FastAPI server exposing the comparison functionality.
    API documentation available at /docs and /redoc.
    """
    from .api import run_api

    console.print(f"[bold blue]🚀 Starting API server at http://{host}:{port}[/bold blue]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    run_api(host=host, port=port, reload=reload)


@app.command(name="completion")
def show_completion(
    shell: Annotated[
        str,
        typer.Argument(help="Shell type: bash, zsh, or fish"),
    ],
) -> None:
    """
    Generate shell completion script.

    Usage:
        city-compare completion bash >> ~/.bashrc
        city-compare completion zsh >> ~/.zshrc
        city-compare completion fish > ~/.config/fish/completions/city-compare.fish
    """
    from .completion import print_completion

    try:
        print_completion(shell)
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1) from e


@app.command(name="complete-city", hidden=True)
def complete_city(
    incomplete: Annotated[str, typer.Argument()] = "",
) -> None:
    """Internal command for city completion (used by shell completion scripts)."""
    from .completion import get_city_completions

    cities = get_city_completions(incomplete)
    for city in cities:
        print(city)


@app.command(name="config")
def config_command(
    init: Annotated[
        bool,
        typer.Option("--init", help="Initialize XDG config with defaults"),
    ] = False,
    copy_local: Annotated[
        bool,
        typer.Option("--copy-local", help="Copy local profiles to XDG config"),
    ] = False,
    show: Annotated[
        bool,
        typer.Option("--show", "-s", help="Show current config paths"),
    ] = False,
) -> None:
    """
    Manage city-compare configuration.

    Uses XDG Base Directory specification:
    - Config: ~/.config/city-compare/
    - Data: ~/.local/share/city-compare/
    - Cache: ~/.cache/city-compare/
    """
    from .xdg import copy_local_config_to_xdg, get_config_info, init_config

    if init:
        created = init_config(force=False)
        if created:
            console.print("[green]✅ Configuration initialisée:[/green]")
            for name, path in created.items():
                console.print(f"  - {name}: {path}")
        else:
            console.print("[yellow]Configuration déjà existante[/yellow]")
        return

    if copy_local:
        copied = copy_local_config_to_xdg()
        if copied:
            console.print("[green]✅ Fichiers copiés:[/green]")
            for name, path in copied.items():
                console.print(f"  - {name}: {path}")
        else:
            console.print("[yellow]Aucun fichier local trouvé[/yellow]")
        return

    # Default: show config info
    info = get_config_info()
    console.print("[bold]📁 Configuration city-compare[/bold]\n")

    console.print("[cyan]Répertoires XDG:[/cyan]")
    console.print(f"  Config: {info['config_dir']} {'✅' if info['config_exists'] else '❌'}")
    console.print(f"  Data:   {info['data_dir']} {'✅' if info['data_exists'] else '❌'}")
    console.print(f"  Cache:  {info['cache_dir']} {'✅' if info['cache_exists'] else '❌'}")

    console.print("\n[cyan]Fichiers actifs:[/cyan]")
    console.print(f"  Profile: {info['profile_path']}")
    console.print(f"  Rules:   {info['rules_path']}")

    console.print("\n[cyan]Base de données:[/cyan]")
    console.print(f"  Cache:    {info['cache_db']}")
    console.print(f"  History:  {info['history_db']}")


@app.command(name="history")
def history_command(
    show: Annotated[
        int | None,
        typer.Option("--show", "-s", help="Show details of a specific entry by ID"),
    ] = None,
    city: Annotated[
        str | None,
        typer.Option("--city", "-c", help="Filter by city name"),
    ] = None,
    winner: Annotated[
        str | None,
        typer.Option("--winner", "-w", help="Filter by winner"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum entries to show"),
    ] = 20,
    stats: Annotated[
        bool,
        typer.Option("--stats", help="Show statistics"),
    ] = False,
    clear: Annotated[
        bool,
        typer.Option("--clear", help="Clear all history"),
    ] = False,
    export_json: Annotated[
        Path | None,
        typer.Option("--export", help="Export history to JSON file"),
    ] = None,
) -> None:
    """
    View and manage comparison history.

    All comparisons are automatically saved and can be reviewed later.
    """
    from .history import ComparisonHistory

    history = ComparisonHistory()

    if show is not None:
        entry = history.get(show)
        if entry is None:
            console.print(f"[red]❌ Entry {show} not found[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]Comparison #{entry.id}[/bold]")
        console.print(f"  Date: {entry.timestamp}")
        console.print(f"  Cities: {', '.join(entry.cities)}")
        console.print(f"  Winner: [green]{entry.winner}[/green]")
        console.print("  Scores:")
        for city_name, score in sorted(entry.scores.items(), key=lambda x: -x[1]):
            console.print(f"    {city_name}: {score:.2f}")
        return

    if stats:
        stats_data = history.get_stats()
        console.print("[bold]📊 Statistiques historique[/bold]\n")
        console.print(f"Total comparaisons: {stats_data['total_comparisons']}")
        console.print(f"Comparaisons (7 derniers jours): {stats_data['comparisons_last_7_days']}")

        if stats_data["top_winners"]:
            console.print("\n[cyan]Top gagnants:[/cyan]")
            for city_name, count in stats_data["top_winners"].items():
                console.print(f"  🏆 {city_name}: {count} victoires")

        if stats_data["most_compared_cities"]:
            console.print("\n[cyan]Villes les plus comparées:[/cyan]")
            for city_name, count in stats_data["most_compared_cities"].items():
                console.print(f"  📊 {city_name}: {count} comparaisons")
        return

    if clear:
        if typer.confirm("Voulez-vous vraiment effacer tout l'historique ?"):
            count = history.clear()
            console.print(f"[green]✅ {count} entrées supprimées[/green]")
        return

    if export_json:
        json_data = history.export_json()
        export_json.write_text(json_data, encoding="utf-8")
        console.print(f"[green]✅ Historique exporté vers {export_json}[/green]")
        return

    # Default: list recent entries
    entries = history.search(city=city, winner=winner, limit=limit)

    if not entries:
        console.print("[yellow]Aucun historique trouvé[/yellow]")
        return

    console.print("[bold]📜 Historique des comparaisons[/bold]\n")
    for entry in entries:
        cities_str = " vs ".join(entry.cities)
        console.print(
            f"  [dim]#{entry.id}[/dim] {entry.timestamp[:10]} | "
            f"{cities_str} → [green]{entry.winner}[/green]"
        )


if __name__ == "__main__":
    app()
