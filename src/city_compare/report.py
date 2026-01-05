"""Report generation for city comparison."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import ComparisonResult, MultiComparisonResult


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


def generate_multi_markdown_report(
    result: MultiComparisonResult,
    explain: bool = False,
    explanations: dict[str, str] | None = None,
) -> str:
    """
    Generate a Markdown report for multi-city comparison.

    Args:
        result: The multi-city comparison result
        explain: Whether to include detailed explanation
        explanations: Dict of city_name -> explanation text

    Returns:
        Markdown formatted report string
    """
    explanations = explanations or {}
    city_names = [s.city_name for s in result.scores]

    lines = [
        f"# Comparaison: {' vs '.join(city_names)}",
        "",
        f"*Généré le {datetime.now().strftime('%Y-%m-%d à %H:%M')}*",
        "",
        "---",
        "",
        "## 🏆 Classement",
        "",
    ]

    # Ranking with medals
    for i, score in enumerate(result.scores):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i + 1}."
        lines.append(f"{medal} **{score.city_name}** - Score: **{score.score:.2f}**")
    lines.extend(["", "---", ""])

    # Build comparison table
    lines.extend(["## 📊 Comparatif détaillé", ""])

    # Table header
    header = "| Métrique |"
    separator = "|----------|"
    for city_name in city_names:
        header += f" {city_name} |"
        separator += "-" * (len(city_name) + 2) + "|"

    lines.extend([header, separator])

    # Rent row
    row = "| 🏠 Loyer (€/m²) |"
    for city_metrics in result.cities:
        row += f" {city_metrics.rent.rent_m2:.2f} |"
    lines.append(row)

    # Temp row
    row = "| 🌡️ Temp. moyenne |"
    for city_metrics in result.cities:
        row += f" {city_metrics.weather.avg_temp_c:.1f}°C |"
    lines.append(row)

    # Rain row
    row = "| 🌧️ Jours de pluie |"
    for city_metrics in result.cities:
        row += f" {city_metrics.weather.rain_days} |"
    lines.append(row)

    # Hot days row
    row = "| ☀️ Jours chauds |"
    for city_metrics in result.cities:
        row += f" {city_metrics.weather.hot_days} |"
    lines.append(row)

    # Score row
    row = "| 📈 **Score** |"
    for city_metrics in result.cities:
        city_score = result.get_city_score(city_metrics.city_name)
        if city_score:
            row += f" **{city_score.score:.2f}** |"
    lines.append(row)

    lines.extend(["", "---", ""])

    # Detailed explanations
    if explain and explanations:
        lines.extend(["## 🔍 Explication détaillée", ""])
        for score in result.scores:
            if score.city_name in explanations:
                lines.extend(
                    [
                        f"### {score.city_name}",
                        "",
                        explanations[score.city_name],
                        "",
                    ]
                )
        lines.extend(["---", ""])

    # Locations
    lines.extend(["## 📍 Localisations", ""])
    for city_metrics in result.cities:
        lines.append(
            f"- **{city_metrics.city_name}**: "
            f"{city_metrics.geo.lat:.4f}, {city_metrics.geo.lon:.4f}"
        )
    lines.extend(["", "---", ""])

    # Configuration
    lines.extend(
        [
            "## ⚙️ Configuration",
            "",
            f"- Profil: `{result.profile_used}`",
            f"- Règles: `{result.rules_used}`",
            "",
        ]
    )

    return "\n".join(lines)


def generate_multi_json_summary(result: MultiComparisonResult) -> dict[str, Any]:
    """
    Generate JSON summary for multi-city comparison.

    Args:
        result: The multi-city comparison result

    Returns:
        Dictionary ready for JSON serialization
    """
    cities_data = {}
    for city in result.cities:
        score = result.get_city_score(city.city_name)
        cities_data[city.city_name] = {
            **city.to_dict(),
            "score": score.score if score else 0,
            "rank": score.rank if score else 0,
            "scoring_variables": score.variables if score else {},
        }

    return {
        "generated_at": datetime.now().isoformat(),
        "cities": cities_data,
        "ranking": result.ranking,
        "winner": result.winner,
        "config": {
            "profile": result.profile_used,
            "rules": result.rules_used,
        },
    }
