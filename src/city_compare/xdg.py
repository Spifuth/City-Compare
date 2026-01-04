"""XDG Base Directory support for city-compare."""

import os
import shutil
from pathlib import Path


def get_xdg_config_home() -> Path:
    """Get XDG_CONFIG_HOME, defaulting to ~/.config."""
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def get_xdg_data_home() -> Path:
    """Get XDG_DATA_HOME, defaulting to ~/.local/share."""
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def get_xdg_cache_home() -> Path:
    """Get XDG_CACHE_HOME, defaulting to ~/.cache."""
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))


def get_config_dir() -> Path:
    """Get the city-compare config directory."""
    return get_xdg_config_home() / "city-compare"


def get_data_dir() -> Path:
    """Get the city-compare data directory."""
    return get_xdg_data_home() / "city-compare"


def get_cache_dir() -> Path:
    """Get the city-compare cache directory."""
    return get_xdg_cache_home() / "city-compare"


def ensure_directories() -> dict[str, Path]:
    """
    Ensure all XDG directories exist.

    Returns:
        Dict mapping directory type to Path.
    """
    dirs = {
        "config": get_config_dir(),
        "data": get_data_dir(),
        "cache": get_cache_dir(),
    }

    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    return dirs


def get_default_profile_path() -> Path:
    """Get the default profile path, preferring XDG config if it exists."""
    xdg_profile = get_config_dir() / "profile.yml"
    local_profile = Path("profiles/default.yml")

    if xdg_profile.exists():
        return xdg_profile
    return local_profile


def get_default_rules_path() -> Path:
    """Get the default rules path, preferring XDG config if it exists."""
    xdg_rules = get_config_dir() / "rules.rules"
    local_rules = Path("profiles/default.rules")

    if xdg_rules.exists():
        return xdg_rules
    return local_rules


def get_cache_db_path() -> Path:
    """Get the cache database path."""
    ensure_directories()
    return get_cache_dir() / "cache.db"


def get_history_db_path() -> Path:
    """Get the history database path."""
    ensure_directories()
    return get_data_dir() / "history.db"


def init_config(force: bool = False) -> dict[str, Path]:
    """
    Initialize XDG config directory with default files.

    Args:
        force: If True, overwrite existing files.

    Returns:
        Dict of created files.
    """
    dirs = ensure_directories()
    created: dict[str, Path] = {}

    # Default profile content
    default_profile = """# City Compare Profile Configuration
# Customize your comparison preferences

# Weather thresholds
rain_threshold_mm: 1.0
hot_threshold_c: 30.0
weather_months: 12

# Rent data path (relative to working directory or absolute)
rent_csv_path: data/loyers_2025.csv
"""

    # Default rules content
    default_rules = """# City Compare Scoring Rules
# Define how cities are scored

# Variables available:
#   rent_m2: Rent per square meter (€)
#   avg_temp_c: Average temperature (°C)
#   rain_days: Number of rainy days per year
#   hot_days: Number of hot days (>30°C) per year

# Score formula
rent_score = 100 - rent_m2 * 5
weather_score = avg_temp_c * 2 - rain_days / 10
score = rent_score + weather_score
"""

    profile_path = dirs["config"] / "profile.yml"
    rules_path = dirs["config"] / "rules.rules"

    if force or not profile_path.exists():
        profile_path.write_text(default_profile)
        created["profile"] = profile_path

    if force or not rules_path.exists():
        rules_path.write_text(default_rules)
        created["rules"] = rules_path

    return created


def copy_local_config_to_xdg() -> dict[str, Path]:
    """
    Copy local profiles to XDG config directory.

    Returns:
        Dict of copied files.
    """
    dirs = ensure_directories()
    copied: dict[str, Path] = {}

    local_profile = Path("profiles/default.yml")
    local_rules = Path("profiles/default.rules")

    if local_profile.exists():
        dest = dirs["config"] / "profile.yml"
        shutil.copy2(local_profile, dest)
        copied["profile"] = dest

    if local_rules.exists():
        dest = dirs["config"] / "rules.rules"
        shutil.copy2(local_rules, dest)
        copied["rules"] = dest

    return copied


def get_config_info() -> dict[str, str | bool]:
    """
    Get information about current config setup.

    Returns:
        Dict with config information.
    """
    config_dir = get_config_dir()
    data_dir = get_data_dir()
    cache_dir = get_cache_dir()

    return {
        "config_dir": str(config_dir),
        "config_exists": config_dir.exists(),
        "data_dir": str(data_dir),
        "data_exists": data_dir.exists(),
        "cache_dir": str(cache_dir),
        "cache_exists": cache_dir.exists(),
        "profile_path": str(get_default_profile_path()),
        "rules_path": str(get_default_rules_path()),
        "cache_db": str(get_cache_db_path()),
        "history_db": str(get_history_db_path()),
    }
