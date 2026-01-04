"""Report generation for city comparison."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import ComparisonResult


def generate_markdown_report(
    result: ComparisonResult,
    explain: bool = False,
    dsl_explanation_a: str = "",
    dsl_explanation_b: str = "",
) -> str:
    """
    Generate a Markdown report from comparison results.

    Args:
        result: The comparison result
        explain: Whether to include detailed explanation
        dsl_explanation_a: DSL explanation for city A
        dsl_explanation_b: DSL explanation for city B

    Returns:
        Markdown formatted report string
    """
    city_a_name = result.city_a.city_name
    city_b_name = result.city_b.city_name
    sep_a = "-" * (len(city_a_name) + 2)
    sep_b = "-" * (len(city_b_name) + 2)

    lines = [
        f"# Comparaison: {city_a_name} vs {city_b_name}",
        "",
        f"*Généré le {datetime.now().strftime('%Y-%m-%d à %H:%M')}*",
        "",
        "---",
        "",
        "## 📊 Résumé",
        "",
        f"| Métrique | {city_a_name} | {city_b_name} |",
        f"|----------|{sep_a}|{sep_b}|",
        f"| 🏠 Loyer (€/m²) | {result.city_a.rent.rent_m2:.2f} "
        f"| {result.city_b.rent.rent_m2:.2f} |",
        f"| 🌡️ Temp. moyenne | {result.city_a.weather.avg_temp_c:.1f}°C "
        f"| {result.city_b.weather.avg_temp_c:.1f}°C |",
        f"| 🌧️ Jours de pluie | {result.city_a.weather.rain_days} "
        f"| {result.city_b.weather.rain_days} |",
        f"| ☀️ Jours chauds (>30°C) | {result.city_a.weather.hot_days} "
        f"| {result.city_b.weather.hot_days} |",
        f"| 📈 **Score** | **{result.score_a.score:.2f}** | **{result.score_b.score:.2f}** |",
        "",
        "---",
        "",
        "## 🏆 Résultat",
        "",
    ]

    # Winner announcement
    if result.score_a.score > result.score_b.score:
        winner = result.city_a.city_name
        diff = result.score_a.score - result.score_b.score
    elif result.score_b.score > result.score_a.score:
        winner = result.city_b.city_name
        diff = result.score_b.score - result.score_a.score
    else:
        winner = None
        diff = 0

    if winner:
        lines.append(f"**🎉 {winner} gagne** avec un avantage de {diff:.2f} points!")
    else:
        lines.append("**🤝 Égalité parfaite!** Les deux villes ont le même score.")

    lines.extend(["", "---", ""])

    # Detailed explanation
    if explain:
        lines.extend(
            [
                "## 🔍 Explication détaillée",
                "",
                f"### {result.city_a.city_name}",
                "",
                dsl_explanation_a,
                "",
                f"### {result.city_b.city_name}",
                "",
                dsl_explanation_b,
                "",
                "---",
                "",
            ]
        )

    # Additional details
    lines.extend(
        [
            "## 📍 Localisation",
            "",
            f"- **{result.city_a.city_name}**: "
            f"{result.city_a.geo.lat:.4f}, {result.city_a.geo.lon:.4f}",
            f"- **{result.city_b.city_name}**: "
            f"{result.city_b.geo.lat:.4f}, {result.city_b.geo.lon:.4f}",
            "",
            "---",
            "",
            "## ⚙️ Configuration",
            "",
            f"- Profil: `{result.profile_used}`",
            f"- Règles: `{result.rules_used}`",
            "",
        ]
    )

    return "\n".join(lines)


def generate_json_summary(
    result: ComparisonResult,
    variables_a: dict[str, float],
    variables_b: dict[str, float],
) -> dict[str, Any]:
    """
    Generate JSON summary from comparison results.

    Args:
        result: The comparison result
        variables_a: All computed variables for city A
        variables_b: All computed variables for city B

    Returns:
        Dictionary ready for JSON serialization
    """
    return {
        "generated_at": datetime.now().isoformat(),
        "cities": {
            result.city_a.city_name: {
                **result.city_a.to_dict(),
                "score": result.score_a.score,
                "scoring_variables": variables_a,
            },
            result.city_b.city_name: {
                **result.city_b.to_dict(),
                "score": result.score_b.score,
                "scoring_variables": variables_b,
            },
        },
        "winner": result.winner,
        "config": {
            "profile": result.profile_used,
            "rules": result.rules_used,
        },
    }


def save_report(content: str, path: Path) -> None:
    """Save report to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def save_json(data: dict[str, Any], path: Path) -> None:
    """Save JSON data to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
