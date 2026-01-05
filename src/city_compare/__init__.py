"""City Compare - Compare French cities and generate reports with explainable scores."""

__version__ = "1.0.0"

from .models import (
    DATA_FR_TO_EN,
    PREFERENCES_FR_TO_EN,
    WEIGHTS_FR_TO_EN,
    ProfileConfig,
    ProfileData,
    ProfilePreferences,
    ProfileWeights,
)
from .scoring import DEFAULT_WEIGHTS, calculate_weighted_score

__all__ = [
    "ProfileConfig",
    "ProfileWeights",
    "ProfilePreferences",
    "ProfileData",
    "WEIGHTS_FR_TO_EN",
    "PREFERENCES_FR_TO_EN",
    "DATA_FR_TO_EN",
    "DEFAULT_WEIGHTS",
    "calculate_weighted_score",
]
