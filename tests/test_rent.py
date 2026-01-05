"""Tests for rent data parsing."""

from pathlib import Path

import pytest

from city_compare.rent import RentDataError, RentDataParser


class TestRentDataParser:
    """Test rent data CSV parsing."""

    def test_parse_valid_csv(self, tmp_path: Path):
        """Test parsing a valid CSV file."""
        csv_content = """commune,loyer_med,departement
Lille,12.5,59
Nantes,11.8,44
Lyon,14.2,69
"""
        csv_file = tmp_path / "loyers.csv"
        csv_file.write_text(csv_content)

        parser = RentDataParser(csv_file)

        rent = parser.get_rent("Lille")
        assert rent.rent_m2 == 12.5
        assert rent.city_name == "Lille"
        assert rent.department == "59"

    def test_parse_csv_with_semicolon(self, tmp_path: Path):
        """Test parsing CSV with semicolon delimiter."""
        csv_content = """commune;loyer_med;departement
Marseille;13.1;13
Bordeaux;12.9;33
"""
        csv_file = tmp_path / "loyers.csv"
        csv_file.write_text(csv_content)

        parser = RentDataParser(csv_file)

        rent = parser.get_rent("Marseille")
        assert rent.rent_m2 == 13.1

    def test_parse_csv_with_french_decimal(self, tmp_path: Path):
        """Test parsing CSV with French comma decimal format (semicolon delimited)."""
        csv_content = """commune;loyer_med;departement
Toulouse;11,5;31
"""
        csv_file = tmp_path / "loyers.csv"
        csv_file.write_text(csv_content)

        parser = RentDataParser(csv_file)

        rent = parser.get_rent("Toulouse")
        assert rent.rent_m2 == 11.5

    def test_city_not_found(self, tmp_path: Path):
        """Test error when city is not found."""
        csv_content = """commune,loyer_med,departement
Lille,12.5,59
"""
        csv_file = tmp_path / "loyers.csv"
        csv_file.write_text(csv_content)

        parser = RentDataParser(csv_file)

        with pytest.raises(RentDataError, match="non trouvée"):
            parser.get_rent("Inconnu")

    def test_file_not_found(self, tmp_path: Path):
        """Test error when CSV file doesn't exist."""
        parser = RentDataParser(tmp_path / "nonexistent.csv")

        with pytest.raises(RentDataError, match="introuvable"):
            parser.get_rent("Lille")

    def test_case_insensitive_search(self, tmp_path: Path):
        """Test that city search is case insensitive."""
        csv_content = """commune,loyer_med,departement
LILLE,12.5,59
"""
        csv_file = tmp_path / "loyers.csv"
        csv_file.write_text(csv_content)

        parser = RentDataParser(csv_file)

        rent = parser.get_rent("lille")
        assert rent.rent_m2 == 12.5

    def test_normalized_search(self, tmp_path: Path):
        """Test that city names are normalized."""
        csv_content = """commune,loyer_med,departement
Saint-Étienne,10.5,42
"""
        csv_file = tmp_path / "loyers.csv"
        csv_file.write_text(csv_content)

        parser = RentDataParser(csv_file)

        rent = parser.get_rent("Saint Étienne")
        assert rent.rent_m2 == 10.5

    def test_list_cities(self, tmp_path: Path):
        """Test listing all cities."""
        csv_content = """commune,loyer_med,departement
Lille,12.5,59
Nantes,11.8,44
Lyon,14.2,69
"""
        csv_file = tmp_path / "loyers.csv"
        csv_file.write_text(csv_content)

        parser = RentDataParser(csv_file)
        cities = parser.list_cities()

        assert len(cities) == 3
        assert "Lille" in cities
        assert "Nantes" in cities
        assert "Lyon" in cities
