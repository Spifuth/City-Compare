"""Data models for city-compare."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator

# ═══════════════════════════════════════════════════════════════════
#  Mapping des clés françaises vers anglaises (rétrocompatibilité)
# ═══════════════════════════════════════════════════════════════════

# Mapping pour les poids (weights)
WEIGHTS_FR_TO_EN = {
    "loyer": "rent_m2",
    "ensoleillement": "sunshine_hours",
    "temperature": "avg_temp",
    "precipitations": "precipitation",
    "qualite_air": "air_quality",
}

# Mapping pour les préférences
PREFERENCES_FR_TO_EN = {
    "temperature_ideale": "ideal_temp",
    "seuil_pluie_mm": "rain_threshold_mm",
    "seuil_canicule_c": "hot_threshold_c",
}

# Mapping pour les données
DATA_FR_TO_EN = {
    "fichier_loyers": "rent_csv_path",
    "historique_meteo_mois": "weather_months",
}


class ProfileWeights(BaseModel):
    """Poids des critères de scoring (doit totaliser 1.0)."""

    rent_m2: float = Field(default=0.35, alias="loyer")
    sunshine_hours: float = Field(default=0.25, alias="ensoleillement")
    avg_temp: float = Field(default=0.20, alias="temperature")
    precipitation: float = Field(default=0.15, alias="precipitations")
    air_quality: float = Field(default=0.05, alias="qualite_air")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def normalize_weights(self) -> "ProfileWeights":
        """Normalise les poids pour qu'ils totalisent 1.0."""
        total = (
            self.rent_m2
            + self.sunshine_hours
            + self.avg_temp
            + self.precipitation
            + self.air_quality
        )
        if abs(total - 1.0) > 0.01:  # Tolérance de 1%
            # Normaliser
            self.rent_m2 /= total
            self.sunshine_hours /= total
            self.avg_temp /= total
            self.precipitation /= total
            self.air_quality /= total
        return self

    def to_dict(self) -> dict[str, float]:
        """Retourne les poids sous forme de dictionnaire."""
        return {
            "rent_m2": self.rent_m2,
            "sunshine_hours": self.sunshine_hours,
            "avg_temp": self.avg_temp,
            "precipitation": self.precipitation,
            "air_quality": self.air_quality,
        }


class ProfilePreferences(BaseModel):
    """Préférences et seuils du profil."""

    ideal_temp: float = Field(default=15.0, alias="temperature_ideale")
    rain_threshold_mm: float = Field(default=1.0, alias="seuil_pluie_mm")
    hot_threshold_c: float = Field(default=30.0, alias="seuil_canicule_c")

    model_config = {"populate_by_name": True}


class ProfileData(BaseModel):
    """Configuration des sources de données."""

    rent_csv_path: Path = Field(default=Path("data/loyers_2025.csv"), alias="fichier_loyers")
    weather_months: int = Field(default=12, alias="historique_meteo_mois")

    model_config = {"populate_by_name": True}


class ProfileConfig(BaseModel):
    """Configuration profile for city comparison.

    Supporte les clés en français et en anglais pour la rétrocompatibilité.
    """

    # Nouveau format structuré
    weights: ProfileWeights = Field(default_factory=ProfileWeights)
    preferences: ProfilePreferences = Field(default_factory=ProfilePreferences)
    data: ProfileData = Field(default_factory=ProfileData)

    # Ancien format (rétrocompatibilité)
    rain_threshold_mm: float = Field(
        default=1.0, description="Precipitation threshold in mm to count as rain day"
    )
    hot_threshold_c: float = Field(
        default=30.0, description="Temperature threshold in °C to count as hot day"
    )
    weather_months: int = Field(
        default=12, description="Number of months of weather history to analyze"
    )
    rent_csv_path: Path = Field(
        default=Path("data/loyers_2025.csv"), description="Path to rent CSV file"
    )

    @model_validator(mode="before")
    @classmethod
    def handle_nested_format(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Gère le nouveau format YAML avec sections imbriquées."""
        if not isinstance(values, dict):
            return values

        # Si on a le nouveau format avec 'weights', 'preferences', 'data'
        if "weights" in values or "preferences" in values or "data" in values:
            # Extraire les préférences vers le format plat pour rétrocompatibilité
            if "preferences" in values and isinstance(values["preferences"], dict):
                prefs = values["preferences"]
                if "seuil_pluie_mm" in prefs:
                    values["rain_threshold_mm"] = prefs["seuil_pluie_mm"]
                if "seuil_canicule_c" in prefs:
                    values["hot_threshold_c"] = prefs["seuil_canicule_c"]

            # Extraire les données vers le format plat
            if "data" in values and isinstance(values["data"], dict):
                data = values["data"]
                if "fichier_loyers" in data:
                    values["rent_csv_path"] = data["fichier_loyers"]
                if "historique_meteo_mois" in data:
                    values["weather_months"] = data["historique_meteo_mois"]

        return values

    @classmethod
    def from_yaml(cls, path: Path) -> "ProfileConfig":
        """Load profile from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        if data is None:
            data = {}
        return cls(**data)

    def get_weights(self) -> dict[str, float]:
        """Retourne les poids pour le scoring."""
        return self.weights.to_dict()

    def get_ideal_temp(self) -> float:
        """Retourne la température idéale."""
        return self.preferences.ideal_temp


@dataclass
class GeoLocation:
    """Geographic coordinates for a city."""

    city_name: str
    lat: float
    lon: float
    display_name: str = ""


@dataclass
class WeatherMetrics:
    """Weather metrics for a city over a period."""

    avg_temp_c: float
    rain_days: int
    hot_days: int
    total_precip_mm: float
    min_temp_c: float
    max_temp_c: float


@dataclass
class RentMetrics:
    """Rent metrics for a city."""

    rent_m2: float
    city_name: str
    department: str = ""


@dataclass
class AirQualityData:
    """Air quality data for a city (optional)."""

    aqi_avg: float
    pm2_5_avg: float
    pm10_avg: float
    good_days: int
    moderate_days: int
    unhealthy_days: int
    quality_label: str = ""


@dataclass
class CityMetrics:
    """All metrics for a city."""

    city_name: str
    geo: GeoLocation
    weather: WeatherMetrics
    rent: RentMetrics
    air_quality: AirQualityData | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "city_name": self.city_name,
            "location": {
                "lat": self.geo.lat,
                "lon": self.geo.lon,
                "display_name": self.geo.display_name,
            },
            "metrics": {
                "rent_m2": self.rent.rent_m2,
                "avg_temp_c": self.weather.avg_temp_c,
                "rain_days": self.weather.rain_days,
                "hot_days": self.weather.hot_days,
                "total_precip_mm": self.weather.total_precip_mm,
                "min_temp_c": self.weather.min_temp_c,
                "max_temp_c": self.weather.max_temp_c,
            },
        }
        if self.air_quality:
            result["air_quality"] = {
                "aqi_avg": self.air_quality.aqi_avg,
                "pm2_5_avg": self.air_quality.pm2_5_avg,
                "pm10_avg": self.air_quality.pm10_avg,
                "good_days": self.air_quality.good_days,
                "moderate_days": self.air_quality.moderate_days,
                "unhealthy_days": self.air_quality.unhealthy_days,
                "quality_label": self.air_quality.quality_label,
            }
        return result


@dataclass
class ScoringResult:
    """Result of scoring a city."""

    city_name: str
    score: float
    rank: int = 0
    variables: dict[str, float] = field(default_factory=dict)
    explanation: str = ""


@dataclass
class ComparisonResult:
    """Full comparison result between two cities."""

    city_a: CityMetrics
    city_b: CityMetrics
    score_a: ScoringResult
    score_b: ScoringResult
    winner: str
    profile_used: str
    rules_used: str


@dataclass
class MultiComparisonResult:
    """Full comparison result between multiple cities."""

    cities: list[CityMetrics]
    scores: list[ScoringResult]
    ranking: list[str]  # City names in order of score (best first)
    profile_used: str
    rules_used: str

    @property
    def winner(self) -> str:
        """Return the top-ranked city."""
        return self.ranking[0] if self.ranking else ""

    def get_city_metrics(self, city_name: str) -> CityMetrics | None:
        """Get metrics for a specific city."""
        for city in self.cities:
            if city.city_name == city_name:
                return city
        return None

    def get_city_score(self, city_name: str) -> ScoringResult | None:
        """Get score for a specific city."""
        for score in self.scores:
            if score.city_name == city_name:
                return score
        return None
