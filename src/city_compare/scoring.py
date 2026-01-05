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


@dataclass
class ConditionalRule:
    """A conditional scoring rule (condition => action)."""

    condition: str
    action: str  # "bonus" or "penalty"
    value: float
    comment: str = ""


class ScoringDSL:
    """
    Mini DSL parser for scoring rules.

    Supports two syntaxes:

    1. Assignment syntax (original):
        variable_name = expression
        score = sunshine_score * 0.3 + rent_score * 0.7

    2. Conditional syntax (new):
        condition => bonus(N)
        condition => penalty(N)

    Expressions can use:
        - Input variables: rent_m2, avg_temp, sunshine_hours, precipitation, aqi
        - Intermediate variables defined earlier
        - Functions: clamp(x, lo, hi), min(a, b), max(a, b), abs(x)
        - Operators: +, -, *, /, (, ), and, or, <, >, <=, >=, ==, !=
        - Numbers (int or float)
    """

    VALID_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")
    CONDITIONAL_PATTERN = re.compile(r"^(.+?)\s*=>\s*(bonus|penalty)\((\d+(?:\.\d+)?)\)$")

    def __init__(self, rules_path: Path | None = None, rules_text: str | None = None):
        self.rules: list[ScoringRule] = []
        self.conditional_rules: list[ConditionalRule] = []
        self._use_conditional_syntax = False

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

            # Skip box-drawing characters (visual separators)
            if line.startswith(("┌", "└", "│", "═", "─")):
                continue

            # Extract inline comment
            comment = ""
            if "#" in line:
                line, comment = line.split("#", 1)
                line = line.strip()
                comment = comment.strip()

            if not line:
                continue

            # Try conditional syntax first (condition => action)
            match = self.CONDITIONAL_PATTERN.match(line)
            if match:
                self._use_conditional_syntax = True
                condition = match.group(1).strip()
                action = match.group(2)
                value = float(match.group(3))
                self.conditional_rules.append(
                    ConditionalRule(
                        condition=condition, action=action, value=value, comment=comment
                    )
                )
                continue

            # Try assignment syntax (name = expression)
            if "=" in line and "=>" not in line:
                name, expression = line.split("=", 1)
                name = name.strip()
                expression = expression.strip()

                # Handle comparison operators in expression (not assignment)
                if expression.startswith("="):
                    # This is == comparison, reconstruct
                    expression = "=" + expression

                if not self.VALID_NAME.match(name):
                    raise ScoringError(
                        f"Ligne {line_num}: nom de variable invalide '{name}'\n"
                        "Les noms doivent commencer par une lettre ou underscore."
                    )

                if not expression:
                    raise ScoringError(f"Ligne {line_num}: expression vide pour '{name}'")

                self.rules.append(ScoringRule(name=name, expression=expression, comment=comment))
                continue

            # Invalid syntax
            raise ScoringError(
                f"Ligne {line_num}: syntaxe invalide\n"
                f"  {line}\n"
                "Attendu: 'nom = expression' ou 'condition => bonus(N)/penalty(N)'"
            )

        # Verify rules based on syntax used
        if not self._use_conditional_syntax and not any(r.name == "score" for r in self.rules):
            raise ScoringError("Le fichier de règles doit définir une variable 'score' finale.")

    def evaluate(
        self,
        rent_m2: float,
        avg_temp_c: float,
        rain_days: int,
        hot_days: int,
        sunshine_hours: float = 0,
        precipitation: float = 0,
        aqi: float = 0,
    ) -> tuple[float, dict[str, float]]:
        """
        Evaluate the scoring rules.

        Args:
            rent_m2: Rent per square meter
            avg_temp_c: Average temperature in Celsius
            rain_days: Number of rainy days
            hot_days: Number of hot days
            sunshine_hours: Annual sunshine hours
            precipitation: Annual precipitation in mm
            aqi: Air quality index

        Returns:
            Tuple of (final_score, all_computed_variables)
        """
        ctx = ScoringContext()
        ctx.variables = {
            "rent_m2": float(rent_m2),
            "avg_temp_c": float(avg_temp_c),
            "avg_temp": float(avg_temp_c),  # Alias
            "rain_days": float(rain_days),
            "hot_days": float(hot_days),
            "sunshine_hours": float(sunshine_hours),
            "precipitation": float(precipitation),
            "aqi": float(aqi),
        }

        # Use conditional rules if present
        if self._use_conditional_syntax:
            return self._evaluate_conditional(ctx)

        # Use assignment rules
        for rule in self.rules:
            try:
                value = self._eval_expression(rule.expression, ctx)
                ctx.variables[rule.name] = value
            except Exception as e:
                raise ScoringError(
                    f"Erreur lors de l'évaluation de '{rule.name} = {rule.expression}':\n  {e}"
                ) from e

        return ctx.variables["score"], ctx.variables.copy()

    def _evaluate_conditional(self, ctx: ScoringContext) -> tuple[float, dict[str, float]]:
        """Evaluate conditional rules and return score with adjustments."""
        adjustments: dict[str, float] = {}
        total_bonus = 0.0
        total_penalty = 0.0

        for rule in self.conditional_rules:
            try:
                # Evaluate condition
                if self._eval_condition(rule.condition, ctx):
                    if rule.action == "bonus":
                        total_bonus += rule.value
                        key = f"bonus_{len(adjustments)}"
                        adjustments[key] = rule.value
                    else:  # penalty
                        total_penalty += rule.value
                        key = f"penalty_{len(adjustments)}"
                        adjustments[key] = -rule.value
            except Exception:
                # Skip rules that fail to evaluate (missing variables, etc.)
                pass

        # Calculate final adjustment
        final_adjustment = total_bonus - total_penalty
        ctx.variables["total_bonus"] = total_bonus
        ctx.variables["total_penalty"] = total_penalty
        ctx.variables["adjustment"] = final_adjustment
        ctx.variables.update(adjustments)

        return final_adjustment, ctx.variables.copy()

    def _eval_condition(self, condition: str, ctx: ScoringContext) -> bool:
        """Evaluate a condition expression."""
        # Replace 'and' and 'or' with Python operators for evaluation
        expr = condition

        # Handle logical operators
        expr = re.sub(r"\band\b", " and ", expr)
        expr = re.sub(r"\bor\b", " or ", expr)

        # Build safe namespace
        namespace = ctx.variables.copy()

        try:
            # Use eval with restricted namespace for condition evaluation
            # This is safe because we control the namespace
            result = eval(expr, {"__builtins__": {}}, namespace)
            return bool(result)
        except Exception:
            return False

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
        input_vars = [
            "rent_m2",
            "avg_temp_c",
            "avg_temp",
            "rain_days",
            "hot_days",
            "sunshine_hours",
            "precipitation",
            "aqi",
        ]
        for name in input_vars:
            if name in variables and variables[name] != 0:
                lines.append(f"- `{name}` = {variables[name]:.2f}")
        lines.append("")

        # Conditional rules explanation
        if self._use_conditional_syntax:
            if variables.get("total_bonus", 0) > 0:
                lines.append("*Bonus appliqués:*")
                lines.append(f"- Total bonus: +{variables['total_bonus']:.0f} points")
            if variables.get("total_penalty", 0) > 0:
                lines.append("*Pénalités appliquées:*")
                lines.append(f"- Total pénalités: -{variables['total_penalty']:.0f} points")
            lines.append("")
            lines.append("*Ajustement final:*")
            adj = variables.get("adjustment", 0)
            sign = "+" if adj >= 0 else ""
            lines.append(f"- Ajustement: **{sign}{adj:.0f}** points")
            return "\n".join(lines)

        # Computed variables (assignment syntax)
        computed = [r for r in self.rules if r.name != "score"]
        if computed:
            lines.append("*Variables intermédiaires:*")
            for rule in computed:
                value = variables.get(rule.name, 0)
                comment = f" ({rule.comment})" if rule.comment else ""
                lines.append(f"- `{rule.name}` = {value:.2f}{comment}")
            lines.append("")

        # Final score
        if any(r.name == "score" for r in self.rules):
            score_rule = next(r for r in self.rules if r.name == "score")
            lines.append("*Score final:*")
            lines.append(f"- `score` = **{variables['score']:.2f}**")
            if score_rule.comment:
                lines.append(f"  > {score_rule.comment}")

        return "\n".join(lines)
