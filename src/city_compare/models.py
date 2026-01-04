"""Data models for city-compare."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    """Configuration profile for city comparison."""

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

    @classmethod
    def from_yaml(cls, path: Path) -> "ProfileConfig":
        """Load profile from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)


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
