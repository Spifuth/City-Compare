"""Tests for profile models."""

import tempfile
from pathlib import Path

from city_compare.models import (
    ProfileConfig,
    ProfilePreferences,
    ProfileWeights,
)


class TestProfileWeights:
    """Test ProfileWeights model."""

    def test_default_weights(self):
        """Test default weights."""
        weights = ProfileWeights()
        assert weights.rent_m2 == 0.35
        assert weights.sunshine_hours == 0.25
        assert weights.avg_temp == 0.20
        assert weights.precipitation == 0.15
        assert weights.air_quality == 0.05

    def test_weights_normalization(self):
        """Test that weights are normalized to sum to 1.0."""
        # Ces poids ne totalisent pas 1.0
        weights = ProfileWeights(
            rent_m2=0.5,
            sunshine_hours=0.5,
            avg_temp=0.5,
            precipitation=0.5,
            air_quality=0.5,
        )
        # Après normalisation, ils devraient totaliser 1.0
        total = (
            weights.rent_m2
            + weights.sunshine_hours
            + weights.avg_temp
            + weights.precipitation
            + weights.air_quality
        )
        assert abs(total - 1.0) < 0.01

    def test_french_aliases(self):
        """Test that French aliases work."""
        weights = ProfileWeights(
            loyer=0.40,
            ensoleillement=0.30,
            temperature=0.15,
            precipitations=0.10,
            qualite_air=0.05,
        )
        assert weights.rent_m2 == 0.40
        assert weights.sunshine_hours == 0.30
        assert weights.avg_temp == 0.15
        assert weights.precipitation == 0.10
        assert weights.air_quality == 0.05

    def test_to_dict(self):
        """Test to_dict method."""
        weights = ProfileWeights()
        d = weights.to_dict()
        assert "rent_m2" in d
        assert "sunshine_hours" in d
        assert "avg_temp" in d
        assert "precipitation" in d
        assert "air_quality" in d


class TestProfilePreferences:
    """Test ProfilePreferences model."""

    def test_default_preferences(self):
        """Test default preferences."""
        prefs = ProfilePreferences()
        assert prefs.ideal_temp == 15.0
        assert prefs.rain_threshold_mm == 1.0
        assert prefs.hot_threshold_c == 30.0

    def test_french_aliases(self):
        """Test that French aliases work."""
        prefs = ProfilePreferences(
            temperature_ideale=18.0,
            seuil_pluie_mm=0.5,
            seuil_canicule_c=32.0,
        )
        assert prefs.ideal_temp == 18.0
        assert prefs.rain_threshold_mm == 0.5
        assert prefs.hot_threshold_c == 32.0


class TestProfileConfig:
    """Test ProfileConfig model."""

    def test_load_default_profile(self):
        """Test loading default profile."""
        config = ProfileConfig.from_yaml(Path("profiles/default.yml"))
        assert config.weights is not None
        weights = config.get_weights()
        assert weights["rent_m2"] == 0.35

    def test_load_sunny_profile(self):
        """Test loading sunny profile."""
        config = ProfileConfig.from_yaml(Path("profiles/sunny.yml"))
        weights = config.get_weights()
        # Sunny profile prioritizes sunshine
        assert weights["sunshine_hours"] == 0.40

    def test_load_budget_profile(self):
        """Test loading budget profile."""
        config = ProfileConfig.from_yaml(Path("profiles/budget.yml"))
        weights = config.get_weights()
        # Budget profile prioritizes rent
        assert weights["rent_m2"] == 0.60

    def test_get_ideal_temp(self):
        """Test getting ideal temperature."""
        config = ProfileConfig.from_yaml(Path("profiles/sunny.yml"))
        assert config.get_ideal_temp() == 18.0

    def test_backward_compatibility(self):
        """Test backward compatibility with old format."""
        # Create old-style profile
        old_yaml = """
rain_threshold_mm: 0.5
hot_threshold_c: 28.0
weather_months: 12
rent_csv_path: "data/loyers_2025.csv"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(old_yaml)
            f.flush()
            config = ProfileConfig.from_yaml(Path(f.name))
            assert config.rain_threshold_mm == 0.5
            assert config.hot_threshold_c == 28.0

    def test_new_format_with_nested_sections(self):
        """Test new format with nested sections."""
        new_yaml = """
weights:
  loyer: 0.40
  ensoleillement: 0.30
  temperature: 0.15
  precipitations: 0.10
  qualite_air: 0.05

preferences:
  temperature_ideale: 17
  seuil_pluie_mm: 0.8
  seuil_canicule_c: 29

data:
  fichier_loyers: "data/loyers_2025.csv"
  historique_meteo_mois: 12
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(new_yaml)
            f.flush()
            config = ProfileConfig.from_yaml(Path(f.name))
            weights = config.get_weights()
            assert weights["rent_m2"] == 0.40
            assert weights["sunshine_hours"] == 0.30
            assert config.get_ideal_temp() == 17.0
            assert config.rain_threshold_mm == 0.8
