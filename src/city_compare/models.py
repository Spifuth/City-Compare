"""Data models for city-compare."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProfileConfig(BaseModel):
    """Configuration profile for city comparison."""

    rain_threshold_mm: float = Field(default=1.0, description="Precipitation threshold in mm to count as rain day")
    hot_threshold_c: float = Field(default=30.0, description="Temperature threshold in °C to count as hot day")
    weather_months: int = Field(default=12, description="Number of months of weather history to analyze")
    rent_csv_path: Path = Field(default=Path("data/loyers_2025.csv"), description="Path to rent CSV file")
    
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
class CityMetrics:
    """All metrics for a city."""

    city_name: str
    geo: GeoLocation
    weather: WeatherMetrics
    rent: RentMetrics

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
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


@dataclass
class ScoringResult:
    """Result of scoring a city."""

    city_name: str
    score: float
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
