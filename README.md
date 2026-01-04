# City-Compare

CLI qui compare 2 villes françaises et génère un rapport détaillé.

## Description

City-Compare est un outil en ligne de commande qui compare deux villes françaises selon plusieurs critères et génère un rapport complet avec scores et explications.

## Fonctionnalités

- **Entrées** : 2 noms de villes + `profile.yml` + `scoring.rules` (mini DSL)
- **Sorties** : `report.md` (rapport markdown) + `summary.json` (résumé JSON)
- **Sources de données** :
  - Géocodage : Nominatim API (avec cache local, respect du rate limit 1 req/s)
  - Météo : Open-Meteo API (données sur 12 mois)
  - Loyers : CSV data.gouv.fr (import manuel dans `rent_data.csv`)
- **Métriques calculées** :
  - Loyer moyen (€/m²)
  - Température moyenne annuelle (°C)
  - Nombre de jours de pluie (>1mm)
  - Nombre de jours chauds (>30°C)

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation

```bash
python city_compare.py <ville1> <ville2> [options]
```

### Options

- `--profile` : Chemin vers le fichier de profil (défaut: `profile.yml`)
- `--rules` : Chemin vers le fichier de règles de scoring (défaut: `scoring.rules`)
- `--rent-csv` : Chemin vers le fichier CSV des loyers (défaut: `rent_data.csv`)

### Exemple

```bash
python city_compare.py Lyon Toulouse
```

Cette commande va :
1. Récupérer les coordonnées géographiques des villes (via Nominatim, avec cache)
2. Télécharger les données météo des 12 derniers mois (via Open-Meteo)
3. Charger les données de loyer depuis `rent_data.csv`
4. Calculer les métriques pour chaque ville
5. Appliquer les règles de scoring définies dans `scoring.rules`
6. Générer `report.md` et `summary.json`

## Configuration

### profile.yml

Fichier de préférences utilisateur (optionnel) :

```yaml
preferences:
  climate: warm
  max_rent: 20
  prefer_dry: true
```

### scoring.rules

Fichier DSL pour définir les règles de scoring. Format :

```
metric operator value -> score
```

Exemple :
```
rent < 15 -> 20
avg_temp > 15 -> 15
rainy_days < 100 -> 10
hot_days < 20 -> 5
```

Opérateurs supportés : `<`, `>`, `<=`, `>=`, `==`

Métriques disponibles :
- `rent` : Loyer en €/m²
- `avg_temp` : Température moyenne en °C
- `rainy_days` : Nombre de jours de pluie
- `hot_days` : Nombre de jours >30°C

### rent_data.csv

Fichier CSV contenant les données de loyer :

```csv
city,rent_per_m2
Paris,30.5
Lyon,16.2
Marseille,14.8
```

## Sorties

### report.md

Rapport markdown avec :
- Comparaison des métriques sous forme de tableau
- Scores calculés pour chaque ville
- Explication détaillée des scores
- Ville gagnante

### summary.json

Résumé JSON structuré avec toutes les données et résultats.

## Cache

Les résultats de géocodage sont mis en cache dans le répertoire `cache/` pour éviter les requêtes répétées et respecter le rate limit de Nominatim (1 requête par seconde).
