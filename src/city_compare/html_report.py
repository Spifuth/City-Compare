"""HTML report generation with interactive charts."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ComparisonResult, MultiComparisonResult


@dataclass
class ChartData:
    """Data for a chart visualization."""

    labels: list[str]
    datasets: list[dict[str, Any]]


def _generate_radar_chart_data(result: MultiComparisonResult) -> str:
    """Generate radar chart data for multi-city comparison."""
    labels = ["Loyer (inv.)", "Température", "Jours sans pluie", "Score final"]

    datasets = []
    colors = [
        "rgba(255, 99, 132, 0.7)",
        "rgba(54, 162, 235, 0.7)",
        "rgba(255, 206, 86, 0.7)",
        "rgba(75, 192, 192, 0.7)",
        "rgba(153, 102, 255, 0.7)",
        "rgba(255, 159, 64, 0.7)",
    ]

    for i, (city, score) in enumerate(zip(result.cities, result.scores, strict=True)):
        # Normalize values for radar chart (0-100 scale)
        rent_inv = max(0, 100 - city.rent.rent_m2 * 5)  # Inverse rent
        temp_norm = min(100, max(0, city.weather.avg_temp_c * 5))  # Temp: 0-20°C -> 0-100
        rain_inv = max(0, 100 - city.weather.rain_days / 2)  # Rain days inverted
        score_norm = min(100, max(0, score.score))

        datasets.append(
            {
                "label": city.city_name,
                "data": [rent_inv, temp_norm, rain_inv, score_norm],
                "backgroundColor": colors[i % len(colors)].replace("0.7", "0.2"),
                "borderColor": colors[i % len(colors)],
                "borderWidth": 2,
            }
        )

    return json.dumps({"labels": labels, "datasets": datasets})


def _generate_bar_chart_data(result: MultiComparisonResult) -> str:
    """Generate bar chart data for score comparison."""
    labels = [score.city_name for score in result.scores]
    scores = [score.score for score in result.scores]

    colors = [
        "rgba(255, 99, 132, 0.7)",
        "rgba(54, 162, 235, 0.7)",
        "rgba(255, 206, 86, 0.7)",
        "rgba(75, 192, 192, 0.7)",
        "rgba(153, 102, 255, 0.7)",
        "rgba(255, 159, 64, 0.7)",
    ]

    return json.dumps(
        {
            "labels": labels,
            "datasets": [
                {
                    "label": "Score",
                    "data": scores,
                    "backgroundColor": colors[: len(labels)],
                    "borderColor": [c.replace("0.7", "1") for c in colors[: len(labels)]],
                    "borderWidth": 1,
                }
            ],
        }
    )


def _generate_weather_chart_data(result: MultiComparisonResult) -> str:
    """Generate weather comparison chart data."""
    labels = [city.city_name for city in result.cities]

    return json.dumps(
        {
            "labels": labels,
            "datasets": [
                {
                    "label": "Temp. moy. (°C)",
                    "data": [city.weather.avg_temp_c for city in result.cities],
                    "backgroundColor": "rgba(255, 99, 132, 0.7)",
                },
                {
                    "label": "Jours de pluie",
                    "data": [city.weather.rain_days for city in result.cities],
                    "backgroundColor": "rgba(54, 162, 235, 0.7)",
                },
                {
                    "label": "Jours chauds (>30°C)",
                    "data": [city.weather.hot_days for city in result.cities],
                    "backgroundColor": "rgba(255, 206, 86, 0.7)",
                },
            ],
        }
    )


def _get_html_template() -> str:
    """Return the HTML template for reports."""
    return """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>City Compare - {title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --primary: #3498db;
            --success: #27ae60;
            --warning: #f39c12;
            --danger: #e74c3c;
            --dark: #2c3e50;
            --light: #ecf0f1;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        .card {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 2rem;
            margin-bottom: 2rem;
        }}
        
        h1 {{
            color: var(--dark);
            text-align: center;
            margin-bottom: 0.5rem;
            font-size: 2.5rem;
        }}
        
        .subtitle {{
            color: #7f8c8d;
            text-align: center;
            margin-bottom: 2rem;
        }}
        
        h2 {{
            color: var(--dark);
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--primary);
        }}
        
        .ranking {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            flex-wrap: wrap;
            margin-bottom: 2rem;
        }}
        
        .rank-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px;
            padding: 1.5rem 2rem;
            text-align: center;
            min-width: 200px;
            transition: transform 0.3s;
        }}
        
        .rank-card:hover {{
            transform: translateY(-5px);
        }}
        
        .rank-card.gold {{
            background: linear-gradient(135deg, #f5af19 0%, #f12711 100%);
        }}
        
        .rank-card.silver {{
            background: linear-gradient(135deg, #bdc3c7 0%, #2c3e50 100%);
        }}
        
        .rank-card.bronze {{
            background: linear-gradient(135deg, #e67e22 0%, #d35400 100%);
        }}
        
        .rank-medal {{
            font-size: 3rem;
            margin-bottom: 0.5rem;
        }}
        
        .rank-city {{
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }}
        
        .rank-score {{
            font-size: 1.2rem;
            opacity: 0.9;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 2rem;
            margin-bottom: 2rem;
        }}
        
        .chart-container {{
            background: #f8f9fa;
            border-radius: 12px;
            padding: 1.5rem;
            height: 400px;
        }}
        
        .chart-title {{
            text-align: center;
            color: var(--dark);
            margin-bottom: 1rem;
            font-size: 1.2rem;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        
        th, td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        
        th {{
            background: var(--primary);
            color: white;
        }}
        
        tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        
        tr:hover {{
            background: #e8f4f8;
        }}
        
        .metric {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-weight: bold;
        }}
        
        .metric-good {{
            background: #d4edda;
            color: #155724;
        }}
        
        .metric-warning {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .metric-bad {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .footer {{
            text-align: center;
            color: white;
            margin-top: 2rem;
            opacity: 0.8;
        }}
        
        @media (max-width: 768px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
            
            .ranking {{
                flex-direction: column;
                align-items: center;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🏙️ City Compare</h1>
            <p class="subtitle">{subtitle}</p>
            
            <div class="ranking">
                {ranking_cards}
            </div>
        </div>
        
        <div class="card">
            <h2>📊 Visualisations</h2>
            <div class="charts-grid">
                <div class="chart-container">
                    <div class="chart-title">Scores par ville</div>
                    <canvas id="barChart"></canvas>
                </div>
                <div class="chart-container">
                    <div class="chart-title">Comparaison multi-critères</div>
                    <canvas id="radarChart"></canvas>
                </div>
            </div>
            <div class="charts-grid">
                <div class="chart-container">
                    <div class="chart-title">Données météo</div>
                    <canvas id="weatherChart"></canvas>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>📋 Données détaillées</h2>
            {data_table}
        </div>
        
        <div class="card">
            <h2>ℹ️ Configuration</h2>
            <p><strong>Profil utilisé:</strong> {profile}</p>
            <p><strong>Règles de scoring:</strong> {rules}</p>
        </div>
    </div>
    
    <div class="footer">
        <p>Généré par City Compare 🏙️</p>
    </div>
    
    <script>
        // Bar Chart
        const barCtx = document.getElementById('barChart').getContext('2d');
        new Chart(barCtx, {{
            type: 'bar',
            data: {bar_data},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true
                    }}
                }}
            }}
        }});
        
        // Radar Chart
        const radarCtx = document.getElementById('radarChart').getContext('2d');
        new Chart(radarCtx, {{
            type: 'radar',
            data: {radar_data},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    r: {{
                        beginAtZero: true,
                        max: 100
                    }}
                }}
            }}
        }});
        
        // Weather Chart
        const weatherCtx = document.getElementById('weatherChart').getContext('2d');
        new Chart(weatherCtx, {{
            type: 'bar',
            data: {weather_data},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'top' }}
                }}
            }}
        }});
    </script>
</body>
</html>"""


def _generate_ranking_cards(result: MultiComparisonResult) -> str:
    """Generate HTML for ranking cards."""
    medals = ["🥇", "🥈", "🥉"]
    classes = ["gold", "silver", "bronze"]

    cards = []
    for i, score in enumerate(result.scores):
        medal = medals[i] if i < 3 else f"#{i + 1}"
        card_class = classes[i] if i < 3 else ""

        cards.append(
            f"""
            <div class="rank-card {card_class}">
                <div class="rank-medal">{medal}</div>
                <div class="rank-city">{score.city_name}</div>
                <div class="rank-score">Score: {score.score:.2f}</div>
            </div>
            """
        )

    return "\n".join(cards)


def _generate_data_table(result: MultiComparisonResult) -> str:
    """Generate HTML table with detailed metrics."""
    rows = []
    for city, score in zip(result.cities, result.scores, strict=True):
        # Determine metric classes
        rent_class = (
            "metric-good"
            if city.rent.rent_m2 < 12
            else "metric-warning"
            if city.rent.rent_m2 < 15
            else "metric-bad"
        )
        temp_class = "metric-good" if 12 <= city.weather.avg_temp_c <= 18 else "metric-warning"
        rain_class = (
            "metric-good"
            if city.weather.rain_days < 120
            else "metric-warning"
            if city.weather.rain_days < 150
            else "metric-bad"
        )

        rows.append(
            f"""
            <tr>
                <td><strong>{city.city_name}</strong></td>
                <td><span class="metric {rent_class}">{city.rent.rent_m2:.1f} €/m²</span></td>
                <td><span class="metric {temp_class}">{city.weather.avg_temp_c:.1f}°C</span></td>
                <td><span class="metric {rain_class}">{city.weather.rain_days} jours</span></td>
                <td>{city.weather.hot_days} jours</td>
                <td><strong>{score.score:.2f}</strong></td>
            </tr>
            """
        )

    return f"""
    <table>
        <thead>
            <tr>
                <th>Ville</th>
                <th>Loyer médian</th>
                <th>Temp. moy.</th>
                <th>Jours de pluie</th>
                <th>Jours chauds</th>
                <th>Score</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
    """


def generate_html_report(result: MultiComparisonResult) -> str:
    """
    Generate a complete HTML report with interactive charts.

    Args:
        result: The multi-city comparison result.

    Returns:
        Complete HTML document as a string.
    """
    template = _get_html_template()

    cities_str = " vs ".join(score.city_name for score in result.scores)

    return template.format(
        title=cities_str,
        subtitle=f"Comparaison de {len(result.cities)} villes françaises",
        ranking_cards=_generate_ranking_cards(result),
        bar_data=_generate_bar_chart_data(result),
        radar_data=_generate_radar_chart_data(result),
        weather_data=_generate_weather_chart_data(result),
        data_table=_generate_data_table(result),
        profile=result.profile_used,
        rules=result.rules_used,
    )


def generate_html_report_two_cities(result: ComparisonResult) -> str:
    """
    Generate HTML report for two-city comparison.

    Converts legacy ComparisonResult to MultiComparisonResult format.

    Args:
        result: The two-city comparison result.

    Returns:
        Complete HTML document as a string.
    """
    from .models import MultiComparisonResult

    # Convert to multi-city format
    scores = sorted(
        [result.score_a, result.score_b],
        key=lambda s: s.score,
        reverse=True,
    )

    multi_result = MultiComparisonResult(
        cities=[result.city_a, result.city_b],
        scores=scores,
        ranking=[s.city_name for s in scores],
        profile_used=result.profile_used,
        rules_used=result.rules_used,
    )

    return generate_html_report(multi_result)


def save_html_report(html: str, path: Path) -> None:
    """Save HTML report to file."""
    path.write_text(html, encoding="utf-8")
