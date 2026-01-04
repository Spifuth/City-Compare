"""Mini DSL parser and scorer for city comparison."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


class ScoringError(Exception):
    """Raised when scoring rules are invalid or evaluation fails."""

    pass


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
    functions: dict[str, Callable] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Built-in functions
        self.functions = {
            "clamp": lambda x, lo, hi: max(lo, min(hi, x)),
            "min": min,
            "max": max,
            "abs": abs,
        }


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
                    f"Ligne {line_num}: syntaxe invalide, attendu 'nom = expression'\n"
                    f"  {line}"
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
            raise ScoringError(
                "Le fichier de règles doit définir une variable 'score' finale."
            )

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
                    f"Erreur lors de l'évaluation de '{rule.name} = {rule.expression}':\n"
                    f"  {e}"
                ) from e

        return ctx.variables["score"], ctx.variables.copy()

    def _eval_expression(self, expr: str, ctx: ScoringContext) -> float:
        """Safely evaluate an expression."""
        # Build safe evaluation namespace
        namespace = {
            **ctx.variables,
            **ctx.functions,
        }
        
        # Validate the expression contains only allowed characters
        allowed = set("0123456789.+-*/() ,_")
        allowed.update(set("abcdefghijklmnopqrstuvwxyz"))
        
        if not all(c in allowed for c in expr):
            invalid = [c for c in expr if c not in allowed]
            raise ScoringError(f"Caractères non autorisés: {invalid}")

        try:
            # Use eval with restricted namespace (no builtins)
            result = eval(expr, {"__builtins__": {}}, namespace)
            return float(result)
        except NameError as e:
            raise ScoringError(f"Variable inconnue: {e}") from e
        except Exception as e:
            raise ScoringError(f"Expression invalide: {e}") from e

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
        lines.append(f"*Score final:*")
        lines.append(f"- `score` = **{variables['score']:.2f}**")
        if score_rule.comment:
            lines.append(f"  > {score_rule.comment}")

        return "\n".join(lines)
