"""Rent data parser for data.gouv CSV files."""

import csv
import re
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Any

from .models import RentMetrics


class RentDataError(Exception):
    """Raised when rent data cannot be found or parsed."""

    pass


class RentDataParser:
    """Parser for the 'Carte des loyers' CSV from data.gouv.fr."""

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self._data: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _normalize_city_name(self, name: str) -> str:
        """Normalize city name for comparison."""
        # Lowercase, remove accents, normalize spaces
        name = name.lower().strip()
        # Common normalizations
        name = re.sub(r"[-''']", " ", name)
        name = re.sub(r"\s+", " ", name)
        # Remove "saint" variations
        name = re.sub(r"\bst\b", "saint", name)
        return name

    def _load_data(self) -> None:
        """Load and parse the CSV file."""
        if self._loaded:
            return

        if not self.csv_path.exists():
            raise RentDataError(
                f"Fichier CSV des loyers introuvable: {self.csv_path}\n"
                "Téléchargez le fichier depuis data.gouv.fr et placez-le dans data/"
            )

        try:
            with open(self.csv_path, encoding="utf-8") as f:
                # Try to detect the delimiter
                sample = f.read(2048)
                f.seek(0)

                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                reader = csv.DictReader(f, dialect=dialect)

                for row in reader:
                    # Handle different possible column names
                    city_name = (
                        row.get("commune")
                        or row.get("COMMUNE")
                        or row.get("nom_commune")
                        or row.get("NOM_COMMUNE")
                        or row.get("libelle_commune")
                        or ""
                    )

                    rent_value = (
                        row.get("loyer_med")
                        or row.get("LOYER_MED")
                        or row.get("loyer_moyen")
                        or row.get("loyer")
                        or row.get("prix_m2")
                        or ""
                    )

                    dept = (
                        row.get("departement")
                        or row.get("DEPARTEMENT")
                        or row.get("code_departement")
                        or row.get("dep")
                        or ""
                    )

                    if city_name and rent_value:
                        try:
                            rent_float = float(rent_value.replace(",", "."))
                            normalized = self._normalize_city_name(city_name)
                            self._data[normalized] = {
                                "city_name": city_name,
                                "rent_m2": rent_float,
                                "department": str(dept),
                            }
                        except ValueError:
                            continue  # Skip rows with invalid rent values

        except Exception as e:
            raise RentDataError(f"Erreur lors de la lecture du CSV: {e}") from e

        self._loaded = True

        if not self._data:
            raise RentDataError(
                "Aucune donnée de loyer valide trouvée dans le CSV. "
                "Vérifiez que le format du fichier est correct."
            )

    def get_rent(self, city_name: str) -> RentMetrics:
        """
        Get rent data for a city.

        Args:
            city_name: Name of the city to look up

        Returns:
            RentMetrics with rent per m²

        Raises:
            RentDataError: If the city is not found in the CSV
        """
        self._load_data()

        normalized = self._normalize_city_name(city_name)

        # Try exact match first
        if normalized in self._data:
            data = self._data[normalized]
            return RentMetrics(
                rent_m2=data["rent_m2"],
                city_name=data["city_name"],
                department=data["department"],
            )

        # Try partial match
        matches = [
            (key, data)
            for key, data in self._data.items()
            if normalized in key or key in normalized
        ]

        if len(matches) == 1:
            key, data = matches[0]
            return RentMetrics(
                rent_m2=data["rent_m2"],
                city_name=data["city_name"],
                department=data["department"],
            )

        if len(matches) > 1:
            suggestions = [self._data[m[0]]["city_name"] for m in matches[:5]]
            raise RentDataError(
                f"Plusieurs communes correspondent à '{city_name}':\n"
                f"  {', '.join(suggestions)}\n"
                "Utilisez le nom exact de la commune."
            )

        # Try fuzzy matching
        suggestions = self._find_similar_cities(normalized, n=5)
        if suggestions:
            suggestion_text = "\n".join(f"  - {s}" for s in suggestions)
            raise RentDataError(
                f"Commune '{city_name}' non trouvée.\nVouliez-vous dire ?\n{suggestion_text}"
            )

        # No match found
        raise RentDataError(
            f"Commune '{city_name}' non trouvée dans le fichier des loyers.\n"
            "Vérifiez l'orthographe ou utilisez le nom officiel de la commune.\n"
            f"Fichier utilisé: {self.csv_path}"
        )

    def _find_similar_cities(self, query: str, n: int = 5) -> list[str]:
        """Find cities with similar names using fuzzy matching."""
        all_normalized = list(self._data.keys())

        # Use difflib's get_close_matches for initial filtering
        close_matches = get_close_matches(query, all_normalized, n=n * 2, cutoff=0.5)

        # Score and sort by similarity
        scored = []
        for match in close_matches:
            ratio = SequenceMatcher(None, query, match).ratio()
            scored.append((ratio, self._data[match]["city_name"]))

        # Sort by score descending
        scored.sort(reverse=True, key=lambda x: x[0])

        return [city for _, city in scored[:n]]

    def search_cities(self, query: str, limit: int = 10) -> list[str]:
        """
        Search for cities matching a query (for autocompletion).

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching city names
        """
        self._load_data()

        normalized_query = self._normalize_city_name(query)
        results = []

        # First: prefix matches
        for key, data in self._data.items():
            if key.startswith(normalized_query):
                results.append((0, data["city_name"]))  # Priority 0 for prefix

        # Second: contains matches
        for key, data in self._data.items():
            if normalized_query in key and not key.startswith(normalized_query):
                results.append((1, data["city_name"]))  # Priority 1 for contains

        # Third: fuzzy matches if not enough results
        if len(results) < limit:
            fuzzy = self._find_similar_cities(normalized_query, n=limit)
            existing = {r[1] for r in results}
            for city in fuzzy:
                if city not in existing:
                    results.append((2, city))  # Priority 2 for fuzzy

        # Sort by priority then alphabetically
        results.sort(key=lambda x: (x[0], x[1]))

        return [city for _, city in results[:limit]]

    def list_cities(self) -> list[str]:
        """List all available cities."""
        self._load_data()
        return sorted(self._data[key]["city_name"] for key in self._data)
