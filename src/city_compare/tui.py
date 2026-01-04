"""Interactive TUI (Text User Interface) for city-compare."""

from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

from .cache import LocalCache
from .geocoding import GeocodingError, NominatimGeocoder
from .models import CityMetrics, ProfileConfig, ScoringResult
from .rent import RentDataError, RentDataParser
from .scoring import ScoringDSL, ScoringError
from .weather import OpenMeteoClient, WeatherError


class CityInputModal(ModalScreen[str | None]):
    """Modal for entering a city name."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, modal_title: str = "Ajouter une ville") -> None:
        super().__init__()
        self.modal_title = modal_title

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label(self.modal_title, id="modal-title")
            yield Input(placeholder="Nom de la ville...", id="city-input")
            with Horizontal(id="modal-buttons"):
                yield Button("Ajouter", id="add-btn", variant="primary")
                yield Button("Annuler", id="cancel-btn", variant="default")

    @on(Button.Pressed, "#add-btn")
    def handle_add(self) -> None:
        input_widget = self.query_one("#city-input", Input)
        city = input_widget.value.strip()
        if city:
            self.dismiss(city)
        else:
            self.notify("Veuillez entrer un nom de ville", severity="warning")

    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class CityCompareApp(App[None]):
    """Interactive TUI application for comparing French cities."""

    CSS = """
    Screen {
        background: $surface;
    }
    
    #main-container {
        width: 100%;
        height: 100%;
        padding: 1;
    }
    
    #top-section {
        height: auto;
        margin-bottom: 1;
    }
    
    #cities-section {
        height: auto;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }
    
    #cities-list {
        height: auto;
        margin-bottom: 1;
    }
    
    #city-buttons {
        height: auto;
    }
    
    #results-section {
        height: 1fr;
        border: solid $secondary;
        padding: 1;
    }
    
    .city-tag {
        background: $primary;
        color: $text;
        padding: 0 1;
        margin: 0 1;
    }
    
    #status-bar {
        height: 3;
        dock: bottom;
        background: $panel;
        padding: 1;
    }
    
    DataTable {
        height: 100%;
    }
    
    #modal-container {
        width: 60;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 2;
    }
    
    #modal-title {
        text-align: center;
        margin-bottom: 1;
        text-style: bold;
    }
    
    #modal-buttons {
        margin-top: 1;
        height: auto;
        align: center middle;
    }
    
    #modal-buttons Button {
        margin: 0 1;
    }
    
    #winner-display {
        text-align: center;
        text-style: bold;
        margin: 1;
        padding: 1;
        background: $success;
        color: $text;
    }
    
    ProgressBar {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quitter"),
        Binding("a", "add_city", "Ajouter ville"),
        Binding("c", "compare", "Comparer"),
        Binding("r", "reset", "Réinitialiser"),
    ]

    def __init__(
        self,
        profile_path: Path = Path("profiles/default.yml"),
        rules_path: Path = Path("profiles/default.rules"),
    ) -> None:
        super().__init__()
        self.profile_path = profile_path
        self.rules_path = rules_path
        self.cities: list[str] = []
        self.metrics: dict[str, CityMetrics] = {}
        self.scores: dict[str, ScoringResult] = {}
        self._config: ProfileConfig | None = None
        self._dsl: ScoringDSL | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Vertical(id="top-section"):
                yield Label("🏙️ City Compare - Comparateur interactif de villes françaises")

            with Container(id="cities-section"):
                yield Label("Villes sélectionnées:", id="cities-label")
                yield Static("(Aucune ville sélectionnée)", id="cities-list")
                with Horizontal(id="city-buttons"):
                    yield Button("➕ Ajouter", id="btn-add", variant="primary")
                    yield Button("🔄 Comparer", id="btn-compare", variant="success")
                    yield Button("🗑️ Réinitialiser", id="btn-reset", variant="warning")

            with Container(id="results-section"):
                yield Label("Résultats:", id="results-label")
                yield Static("", id="winner-display")
                yield DataTable(id="results-table")

            yield Static("", id="status-bar")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app on mount."""
        self._load_config()
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Rang", "Ville", "Score", "Loyer", "Temp.", "Pluie")
        self._update_status("Prêt - Appuyez sur 'a' pour ajouter une ville")

    def _load_config(self) -> None:
        """Load profile and rules."""
        try:
            self._config = ProfileConfig.from_yaml(self.profile_path)
            self._dsl = ScoringDSL(rules_path=self.rules_path)
            self._update_status(f"Configuration chargée: {self.profile_path.name}")
        except (FileNotFoundError, ScoringError) as e:
            self.notify(f"Erreur de configuration: {e}", severity="error")

    def _update_cities_display(self) -> None:
        """Update the cities list display."""
        cities_list = self.query_one("#cities-list", Static)
        if self.cities:
            cities_list.update(" | ".join(f"🏠 {city}" for city in self.cities))
        else:
            cities_list.update("(Aucune ville sélectionnée)")

    def _update_status(self, message: str) -> None:
        """Update the status bar."""
        status = self.query_one("#status-bar", Static)
        status.update(f"ℹ️ {message}")

    @on(Button.Pressed, "#btn-add")
    def action_add_city(self) -> None:
        """Open modal to add a city."""

        def on_city_selected(city: str | None) -> None:
            if city and city not in self.cities:
                self.cities.append(city)
                self._update_cities_display()
                self._update_status(f"Ville ajoutée: {city}")
            elif city in self.cities:
                self.notify(f"{city} est déjà dans la liste", severity="warning")

        self.push_screen(CityInputModal(), on_city_selected)

    @on(Button.Pressed, "#btn-compare")
    def action_compare(self) -> None:
        """Run the comparison."""
        if len(self.cities) < 2:
            self.notify("Au moins 2 villes sont requises", severity="warning")
            return

        if not self._config or not self._dsl:
            self.notify("Configuration non chargée", severity="error")
            return

        self._run_comparison()

    @on(Button.Pressed, "#btn-reset")
    def action_reset(self) -> None:
        """Reset the app state."""
        self.cities.clear()
        self.metrics.clear()
        self.scores.clear()
        self._update_cities_display()

        table = self.query_one("#results-table", DataTable)
        table.clear()

        winner_display = self.query_one("#winner-display", Static)
        winner_display.update("")

        self._update_status("Application réinitialisée")

    def _run_comparison(self) -> None:
        """Run the city comparison."""
        if not self._config or not self._dsl:
            return

        self._update_status("Comparaison en cours...")

        # Initialize services
        cache = LocalCache()
        geocoder = NominatimGeocoder(cache)
        weather_client = OpenMeteoClient(cache)
        rent_parser = RentDataParser(self._config.rent_csv_path)

        # Collect metrics
        self.metrics.clear()
        self.scores.clear()

        for city in self.cities:
            try:
                geo = geocoder.geocode(city)
                weather = weather_client.get_weather(geo, self._config)
                rent = rent_parser.get_rent(city)

                metrics = CityMetrics(
                    city_name=city,
                    geo=geo,
                    weather=weather,
                    rent=rent,
                )
                self.metrics[city] = metrics

                # Calculate score
                score_value, variables = self._dsl.evaluate(
                    rent.rent_m2,
                    weather.avg_temp_c,
                    weather.rain_days,
                    weather.hot_days,
                )
                self.scores[city] = ScoringResult(
                    city_name=city,
                    score=score_value,
                    variables=variables,
                )

            except (GeocodingError, WeatherError, RentDataError) as e:
                self.notify(f"Erreur pour {city}: {e}", severity="error")
                return

        # Sort by score
        sorted_scores = sorted(self.scores.values(), key=lambda s: s.score, reverse=True)
        for i, score in enumerate(sorted_scores):
            score.rank = i + 1

        # Update table
        table = self.query_one("#results-table", DataTable)
        table.clear()

        for score in sorted_scores:
            metrics = self.metrics[score.city_name]
            medal = ["🥇", "🥈", "🥉"][score.rank - 1] if score.rank <= 3 else str(score.rank)
            table.add_row(
                medal,
                score.city_name,
                f"{score.score:.2f}",
                f"{metrics.rent.rent_m2:.1f} €/m²",
                f"{metrics.weather.avg_temp_c:.1f}°C",
                f"{metrics.weather.rain_days} j",
            )

        # Update winner display
        winner = sorted_scores[0].city_name
        winner_display = self.query_one("#winner-display", Static)
        winner_display.update(f"🏆 Gagnant: {winner} avec un score de {sorted_scores[0].score:.2f}")

        self._update_status(f"Comparaison terminée - {winner} gagne!")


def run_tui(
    profile: Path = Path("profiles/default.yml"),
    rules: Path = Path("profiles/default.rules"),
) -> None:
    """Run the TUI application."""
    app = CityCompareApp(profile_path=profile, rules_path=rules)
    app.run()
