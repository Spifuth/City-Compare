"""REST API for city-compare using FastAPI."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .cache import LocalCache
from .geocoding import GeocodingError, NominatimGeocoder
from .models import ProfileConfig
from .rent import RentDataError, RentDataParser
from .scoring import ScoringDSL, ScoringError
from .weather import OpenMeteoClient, WeatherError

# API models
class CityScore(BaseModel):
    """Score result for a city."""

    city_name: str
    score: float
    rank: int
    variables: dict[str, float]


class CityMetricsResponse(BaseModel):
    """Detailed metrics for a city."""

    city_name: str
    location: str
    rent_m2: float
    avg_temp_c: float
    rain_days: int
    hot_days: int
    min_temp_c: float
    max_temp_c: float
    total_precip_mm: float


class ComparisonRequest(BaseModel):
    """Request body for comparison."""

    cities: list[str] = Field(..., min_length=2, description="List of cities to compare")
    profile: str = Field(default="profiles/default.yml", description="Profile path")
    rules: str = Field(default="profiles/default.rules", description="Rules path")


class ComparisonResponse(BaseModel):
    """Response for comparison endpoint."""

    winner: str
    ranking: list[str]
    scores: list[CityScore]
    metrics: list[CityMetricsResponse]
    profile_used: str
    rules_used: str


class CitySearchResponse(BaseModel):
    """Response for city search."""

    cities: list[str]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


# FastAPI app
app = FastAPI(
    title="City Compare API",
    description="API pour comparer des villes françaises sur différents critères",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# Dependency for shared services
def get_cache() -> LocalCache:
    """Get cache instance."""
    return LocalCache()


def get_geocoder(cache: Annotated[LocalCache, Depends(get_cache)]) -> NominatimGeocoder:
    """Get geocoder instance."""
    return NominatimGeocoder(cache)


def get_weather_client(cache: Annotated[LocalCache, Depends(get_cache)]) -> OpenMeteoClient:
    """Get weather client instance."""
    return OpenMeteoClient(cache)


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    from . import __version__

    return HealthResponse(status="healthy", version=__version__)


@app.get("/cities/search", response_model=CitySearchResponse, tags=["Cities"])
async def search_cities(
    q: Annotated[str, Query(description="Search query")],
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum results")] = 20,
) -> CitySearchResponse:
    """
    Search for cities in the rent database.

    Returns cities matching the query (case-insensitive, partial match).
    """
    try:
        config = ProfileConfig.from_yaml(Path("profiles/default.yml"))
        parser = RentDataParser(config.rent_csv_path)
        all_cities = parser.list_cities()

        # Filter cities matching query
        query_lower = q.lower()
        matching = [city for city in all_cities if query_lower in city.lower()][:limit]

        return CitySearchResponse(cities=matching, total=len(matching))
    except (FileNotFoundError, RentDataError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/cities", response_model=CitySearchResponse, tags=["Cities"])
async def list_all_cities(
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum results")] = 100,
) -> CitySearchResponse:
    """
    List all available cities in the rent database.
    """
    try:
        config = ProfileConfig.from_yaml(Path("profiles/default.yml"))
        parser = RentDataParser(config.rent_csv_path)
        all_cities = parser.list_cities()[:limit]

        return CitySearchResponse(cities=all_cities, total=len(all_cities))
    except (FileNotFoundError, RentDataError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/cities/{city_name}", response_model=CityMetricsResponse, tags=["Cities"])
async def get_city_metrics(
    city_name: str,
    geocoder: Annotated[NominatimGeocoder, Depends(get_geocoder)],
    weather_client: Annotated[OpenMeteoClient, Depends(get_weather_client)],
) -> CityMetricsResponse:
    """
    Get detailed metrics for a single city.
    """
    try:
        config = ProfileConfig.from_yaml(Path("profiles/default.yml"))
        rent_parser = RentDataParser(config.rent_csv_path)

        geo = geocoder.geocode(city_name)
        weather = weather_client.get_weather(geo, config)
        rent = rent_parser.get_rent(city_name)

        return CityMetricsResponse(
            city_name=city_name,
            location=geo.display_name,
            rent_m2=rent.rent_m2,
            avg_temp_c=weather.avg_temp_c,
            rain_days=weather.rain_days,
            hot_days=weather.hot_days,
            min_temp_c=weather.min_temp_c,
            max_temp_c=weather.max_temp_c,
            total_precip_mm=weather.total_precip_mm,
        )
    except GeocodingError as e:
        raise HTTPException(status_code=404, detail=f"City not found: {e}") from e
    except (WeatherError, RentDataError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/compare", response_model=ComparisonResponse, tags=["Comparison"])
async def compare_cities(
    request: ComparisonRequest,
    geocoder: Annotated[NominatimGeocoder, Depends(get_geocoder)],
    weather_client: Annotated[OpenMeteoClient, Depends(get_weather_client)],
) -> ComparisonResponse:
    """
    Compare multiple cities and return ranked results.

    Requires at least 2 cities. Returns scores based on the specified
    profile and scoring rules.
    """
    try:
        # Load config and rules
        config = ProfileConfig.from_yaml(Path(request.profile))
        dsl = ScoringDSL(rules_path=Path(request.rules))
        rent_parser = RentDataParser(config.rent_csv_path)

        # Collect metrics for all cities
        all_metrics: list[CityMetricsResponse] = []
        all_scores: list[CityScore] = []

        for city in request.cities:
            geo = geocoder.geocode(city)
            weather = weather_client.get_weather(geo, config)
            rent = rent_parser.get_rent(city)

            metrics = CityMetricsResponse(
                city_name=city,
                location=geo.display_name,
                rent_m2=rent.rent_m2,
                avg_temp_c=weather.avg_temp_c,
                rain_days=weather.rain_days,
                hot_days=weather.hot_days,
                min_temp_c=weather.min_temp_c,
                max_temp_c=weather.max_temp_c,
                total_precip_mm=weather.total_precip_mm,
            )
            all_metrics.append(metrics)

            # Calculate score
            score_value, variables = dsl.evaluate(
                rent.rent_m2,
                weather.avg_temp_c,
                weather.rain_days,
                weather.hot_days,
            )
            all_scores.append(
                CityScore(
                    city_name=city,
                    score=score_value,
                    rank=0,  # Will be set after sorting
                    variables=variables,
                )
            )

        # Sort by score descending and assign ranks
        sorted_scores = sorted(all_scores, key=lambda s: s.score, reverse=True)
        for i, score in enumerate(sorted_scores):
            score.rank = i + 1

        ranking = [s.city_name for s in sorted_scores]
        winner = ranking[0]

        return ComparisonResponse(
            winner=winner,
            ranking=ranking,
            scores=sorted_scores,
            metrics=all_metrics,
            profile_used=request.profile,
            rules_used=request.rules,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}") from e
    except GeocodingError as e:
        raise HTTPException(status_code=404, detail=f"City not found: {e}") from e
    except (WeatherError, RentDataError, ScoringError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app."""
    return app


def run_api(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """Run the API server."""
    import uvicorn

    uvicorn.run(
        "city_compare.api:app",
        host=host,
        port=port,
        reload=reload,
    )
