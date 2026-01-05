# 🏙️ City-Compare

CLI pour comparer 2 villes françaises et générer un rapport avec un score explicable.

[![CI](https://github.com/Spifuth/City-Compare/actions/workflows/ci.yml/badge.svg)](https://github.com/Spifuth/City-Compare/actions/workflows/ci.yml)

## ✨ Fonctionnalités

- **Géocodage automatique** via Nominatim (OpenStreetMap)
- **Données météo 12 mois** via Open-Meteo archive
- **Loyers** depuis le CSV "Carte des loyers" (data.gouv.fr)
- **Mini DSL** pour définir vos propres règles de scoring
- **Rapports** en Markdown et JSON
- **Cache local** SQLite pour limiter les appels API

## 📦 Installation

```bash
# Cloner le repo
git clone https://github.com/Spifuth/City-Compare.git
cd City-Compare

# Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# Installer
pip install -e .

# Ou avec les dépendances de développement
pip install -e ".[dev]"
```

## 📊 Données requises

### Loyers (obligatoire)

Téléchargez le CSV des loyers depuis [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2024/) et placez-le dans `data/loyers_2025.csv`.

Le CSV doit contenir au minimum les colonnes :
- `commune` (nom de la ville)
- `loyer_med` (loyer médian €/m²)

## 🚀 Utilisation

### Comparaison basique

```bash
city-compare compare "Lille" "Nantes"
```

### Avec options

```bash
city-compare compare "Lyon" "Bordeaux" \
    --profile profiles/default.yml \
    --rules profiles/default.rules \
    --out report.md \
    --json summary.json \
    --explain
```

### Options disponibles

| Option | Description |
|--------|-------------|
| `--profile, -p` | Fichier YAML de configuration |
| `--rules, -r` | Fichier de règles de scoring |
| `--out, -o` | Chemin du rapport Markdown |
| `--json, -j` | Chemin du résumé JSON |
| `--explain, -e` | Inclut l'explication détaillée du scoring |

### Vider le cache

```bash
city-compare clear-cache
```

## ⚙️ Configuration

### Profil (`profiles/default.yml`)

```yaml
# Seuil de précipitation pour compter un jour de pluie (mm)
rain_threshold_mm: 1.0

# Seuil de température pour compter un jour chaud (°C)
hot_threshold_c: 30.0

# Mois d'historique météo à analyser
weather_months: 12

# Chemin vers le CSV des loyers
rent_csv_path: "data/loyers_2025.csv"
```

### Règles de scoring (`profiles/default.rules`)

Le mini DSL permet de définir comment calculer le score final.

**Variables d'entrée disponibles :**
- `rent_m2` : loyer €/m²
- `avg_temp_c` : température moyenne (°C)
- `rain_days` : nombre de jours de pluie
- `hot_days` : nombre de jours > seuil chaleur

**Fonctions disponibles :**
- `clamp(x, min, max)` : limite x entre min et max
- `min(a, b)` : minimum
- `max(a, b)` : maximum
- `abs(x)` : valeur absolue

**Exemple :**

```
# Normaliser le loyer (moins cher = mieux)
rent_score = clamp((25 - rent_m2) / (25 - 8) * 100, 0, 100)

# Score température (15°C idéal)
temp_score = clamp(100 - abs(avg_temp_c - 15) * 5, 0, 100)

# Pénalité pluie
rain_score = clamp((200 - rain_days) / 200 * 100, 0, 100)

# Score final : 55% loyer, 45% météo
weather = 0.6 * temp_score + 0.4 * rain_score
score = 0.55 * rent_score + 0.45 * weather
```

## 📄 Exemple de rapport

```markdown
# Comparaison: Lille vs Nantes

## 📊 Résumé

| Métrique | Lille | Nantes |
|----------|-------|--------|
| 🏠 Loyer (€/m²) | 12.50 | 11.80 |
| 🌡️ Temp. moyenne | 11.2°C | 12.8°C |
| 🌧️ Jours de pluie | 125 | 118 |
| ☀️ Jours chauds | 8 | 12 |
| 📈 **Score** | **68.42** | **71.15** |

## 🏆 Résultat

**🎉 Nantes gagne** avec un avantage de 2.73 points!
```

## 🧪 Tests

```bash
# Lancer les tests
pytest tests/ -v

# Avec couverture
pytest tests/ -v --cov=city_compare
```

## 🔧 Développement

```bash
# Linting
ruff check src/
ruff format src/

# Type checking
mypy src/
```

## 📁 Structure du projet

```
city-compare/
├── src/city_compare/
│   ├── __init__.py
│   ├── cache.py       # Cache SQLite local
│   ├── cli.py         # Interface ligne de commande
│   ├── geocoding.py   # Client Nominatim
│   ├── models.py      # Modèles de données
│   ├── rent.py        # Parser CSV loyers
│   ├── report.py      # Génération de rapports
│   ├── scoring.py     # Mini DSL scoring
│   └── weather.py     # Client Open-Meteo
├── profiles/
│   ├── default.yml    # Profil par défaut
│   ├── sunny.yml      # Profil chasseur de soleil
│   └── default.rules  # Règles scoring par défaut
├── tests/
│   ├── test_cache.py
│   ├── test_rent.py
│   └── test_scoring.py
├── data/              # Données (non versionnées)
│   └── loyers_2025.csv
├── pyproject.toml
└── README.md
```

## 📝 License

MIT
