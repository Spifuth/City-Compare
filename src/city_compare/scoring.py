"""Mini DSL parser and scorer for city comparison."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .ast_parser import SafeExpressionError, SafeExpressionEvaluator


class ScoringError(Exception):
    """Raised when scoring rules are invalid or evaluation fails."""

    pass


# ═══════════════════════════════════════════════════════════════════
#  Poids par défaut pour le scoring
# ═══════════════════════════════════════════════════════════════════

DEFAULT_WEIGHTS = {
    "rent_m2": 0.35,
    "sunshine_hours": 0.25,
    "avg_temp": 0.20,
    "precipitation": 0.15,
    "air_quality": 0.05,
}


@dataclass
class ScoringRule:
    """A single scoring rule from the DSL."""

    name: str
    expression: str
    comment: str = ""


@dataclass
class ScoringContext:
    """Context for evaluating scoring expressions."""

    variables: dict[str, float] = field(default_factory=dict)
    functions: dict[str, Callable[..., float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Built-in functions
        self.functions = {
            "clamp": lambda x, lo, hi: max(lo, min(hi, x)),
            "min": min,
            "max": max,
            "abs": abs,
        }


def calculate_weighted_score(
    rent_m2: float,
    sunshine_hours: float,
    avg_temp: float,
    precipitation: float,
    air_quality: float | None = None,
    weights: dict[str, float] | None = None,
    ideal_temp: float = 15.0,
) -> tuple[float, dict[str, float]]:
    """Calcule le score pondéré d'une ville.

    Args:
        rent_m2: Loyer au m²
        sunshine_hours: Heures d'ensoleillement annuelles
        avg_temp: Température moyenne annuelle (°C)
        precipitation: Précipitations annuelles (mm)
        air_quality: Indice qualité de l'air (optionnel)
        weights: Poids des critères (utilise DEFAULT_WEIGHTS si None)
        ideal_temp: Température idéale (défaut: 15°C)

    Returns:
        Tuple (score_final, détail_scores)
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()

    # Normalisation des métriques sur 0-100
    # Loyer: moins cher = mieux (inversé, basé sur 8-25€/m²)
    rent_score = max(0, min(100, (25 - rent_m2) / (25 - 8) * 100))

    # Ensoleillement: plus = mieux (basé sur 1500-3000h)
    sun_score = max(0, min(100, (sunshine_hours - 1500) / (3000 - 1500) * 100))

    # Température: proche de l'idéal = mieux
    temp_diff = abs(avg_temp - ideal_temp)
    temp_score = max(0, 100 - temp_diff * 8)  # -8 pts par °C d'écart

    # Précipitations: moins = mieux (basé sur 500-1500mm)
    precip_score = max(0, min(100, (1500 - precipitation) / (1500 - 500) * 100))

    # Qualité de l'air: AQI bas = mieux (basé sur 0-100 AQI)
    air_score = max(0, 100 - air_quality) if air_quality is not None else 50

    # Calcul du score pondéré
    score = (
        weights.get("rent_m2", 0.35) * rent_score
        + weights.get("sunshine_hours", 0.25) * sun_score
        + weights.get("avg_temp", 0.20) * temp_score
        + weights.get("precipitation", 0.15) * precip_score
        + weights.get("air_quality", 0.05) * air_score
    )

    details = {
        "rent_score": rent_score,
        "sun_score": sun_score,
        "temp_score": temp_score,
        "precip_score": precip_score,
        "air_score": air_score,
        "final_score": score,
    }

    return score, details


class ScoringDSL:
    """
    Mini DSL parser for scoring rules.

    Syntax:
        # Comment
        variable_name = expression

    Expressions can use:
        - Input variables: rent_m2, avg_temp_c, rain_days, hot_days
        - Intermediate variables defined earlier
        - Functions: clamp(x, lo, hi), min(a, b), max(a, b), abs(x)
        - Operators: +, -, *, /, (, )
        - Numbers (int or float)

    The final 'score' variable is the output.
    """

    VALID_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")

    def __init__(self, rules_path: Path | None = None, rules_text: str | None = None):
        self.rules: list[ScoringRule] = []

        if rules_path:
            self._parse_file(rules_path)
        elif rules_text:
            self._parse_text(rules_text)

    def _parse_file(self, path: Path) -> None:
        """Parse rules from a file."""
        if not path.exists():
            raise ScoringError(f"Fichier de règles introuvable: {path}")

        with open(path) as f:
            self._parse_text(f.read())

    def _parse_text(self, text: str) -> None:
        """Parse rules from text."""
        for line_num, line in enumerate(text.splitlines(), 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Extract inline comment
            comment = ""
            if "#" in line:
                line, comment = line.split("#", 1)
                line = line.strip()
                comment = comment.strip()

            # Parse assignment
            if "=" not in line:
                raise ScoringError(
                    f"Ligne {line_num}: syntaxe invalide, attendu 'nom = expression'\n  {line}"
                )

            name, expression = line.split("=", 1)
            name = name.strip()
            expression = expression.strip()

            if not self.VALID_NAME.match(name):
                raise ScoringError(
                    f"Ligne {line_num}: nom de variable invalide '{name}'\n"
                    "Les noms doivent commencer par une lettre ou underscore."
                )

            if not expression:
                raise ScoringError(f"Ligne {line_num}: expression vide pour '{name}'")

            self.rules.append(ScoringRule(name=name, expression=expression, comment=comment))

        # Verify 'score' is defined
        if not any(r.name == "score" for r in self.rules):
            raise ScoringError("Le fichier de règles doit définir une variable 'score' finale.")

    def evaluate(
        self,
        rent_m2: float,
        avg_temp_c: float,
        rain_days: int,
        hot_days: int,
    ) -> tuple[float, dict[str, float]]:
        """
        Evaluate the scoring rules.

        Args:
            rent_m2: Rent per square meter
            avg_temp_c: Average temperature in Celsius
            rain_days: Number of rainy days
            hot_days: Number of hot days

        Returns:
            Tuple of (final_score, all_computed_variables)
        """
        ctx = ScoringContext()
        ctx.variables = {
            "rent_m2": float(rent_m2),
            "avg_temp_c": float(avg_temp_c),
            "rain_days": float(rain_days),
            "hot_days": float(hot_days),
        }

        for rule in self.rules:
            try:
                value = self._eval_expression(rule.expression, ctx)
                ctx.variables[rule.name] = value
            except Exception as e:
                raise ScoringError(
                    f"Erreur lors de l'évaluation de '{rule.name} = {rule.expression}':\n  {e}"
                ) from e

        return ctx.variables["score"], ctx.variables.copy()

    def _eval_expression(self, expr: str, ctx: ScoringContext) -> float:
        """Safely evaluate an expression using AST parser."""
        evaluator = SafeExpressionEvaluator(ctx.variables, ctx.functions)
        try:
            return evaluator.evaluate(expr)
        except SafeExpressionError as e:
            raise ScoringError(str(e)) from e

    def get_explanation(self, variables: dict[str, float]) -> str:
        """Generate a human-readable explanation of the scoring."""
        lines = ["**Calcul du score:**", ""]

        # Input variables
        lines.append("*Variables d'entrée:*")
        for name in ["rent_m2", "avg_temp_c", "rain_days", "hot_days"]:
            if name in variables:
                lines.append(f"- `{name}` = {variables[name]:.2f}")
        lines.append("")

        # Computed variables
        computed = [r for r in self.rules if r.name != "score"]
        if computed:
            lines.append("*Variables intermédiaires:*")
            for rule in computed:
                value = variables.get(rule.name, 0)
                comment = f" ({rule.comment})" if rule.comment else ""
                lines.append(f"- `{rule.name}` = {value:.2f}{comment}")
            lines.append("")

        # Final score
        score_rule = next(r for r in self.rules if r.name == "score")
        lines.append("*Score final:*")
        lines.append(f"- `score` = **{variables['score']:.2f}**")
        if score_rule.comment:
            lines.append(f"  > {score_rule.comment}")

        return "\n".join(lines)
