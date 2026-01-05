# 📁 Profils City-Compare

Ce dossier contient les profils de configuration et règles de scoring.

## 🎯 Profils disponibles

| Profil | Description | Priorité |
|--------|-------------|----------|
| `default.yml` | 🏠 Équilibré | Budget (35%) + Météo (60%) |
| `sunny.yml` | ☀️ Chasseur de soleil | Ensoleillement (40%) |
| `budget.yml` | 💰 Budget serré | Loyer (60%) |
| `qualite_vie.yml` | 🌿 Qualité de vie | Air pur (25%) + Climat |
| `retraite.yml` | 🏖️ Retraite dorée | Climat doux (70%) |

## 📐 Fichiers de règles

| Fichier | Description |
|---------|-------------|
| `default.rules` | Règles équilibrées |
| `weather_priority.rules` | Bonus météo généreux |
| `budget.rules` | Bonus loyer généreux |
| `qualite_vie.rules` | Focus qualité de l'air |
| `retraite.rules` | Climat méditerranéen |

## 🚀 Utilisation

### Avec un profil seul
```bash
city-compare compare "Lyon" "Nantes" --profile profiles/sunny.yml
```

### Avec profil + règles
```bash
city-compare compare "Lyon" "Nantes" \
  --profile profiles/sunny.yml \
  --rules profiles/weather_priority.rules
```

### Avec qualité de l'air
```bash
city-compare compare "Lyon" "Nice" \
  --profile profiles/qualite_vie.yml \
  --air-quality
```

## ⚙️ Structure d'un profil YAML

```yaml
# Pondération (doit totaliser 1.0)
weights:
  loyer: 0.35           # 35% du score
  ensoleillement: 0.25  # 25% du score
  temperature: 0.20     # 20% du score
  precipitations: 0.15  # 15% du score
  qualite_air: 0.05     # 5% du score

# Préférences
preferences:
  temperature_ideale: 15    # °C optimal
  seuil_pluie_mm: 1.0       # mm pour jour pluvieux
  seuil_canicule_c: 30      # °C pour jour très chaud

# Sources de données
data:
  fichier_loyers: "data/loyers_2025.csv"
  historique_meteo_mois: 12
```

## 📐 Structure d'un fichier de règles

```
# Syntaxe: condition => action
# Variables: sunshine_hours, avg_temp, precipitation, rent_m2, aqi

# Exemples
sunshine_hours > 2500 => bonus(10)
rent_m2 < 10 => bonus(15)
aqi > 70 => penalty(10)

# Conditions combinées
sunshine_hours > 2500 and avg_temp > 14 => bonus(20)
```

## 🔧 Créer son propre profil

1. Copiez un profil existant
2. Ajustez les `weights` selon vos priorités
3. Modifiez les `preferences` si nécessaire
4. Optionnel: créez un fichier `.rules` associé

```bash
cp profiles/default.yml profiles/mon_profil.yml
# Éditez mon_profil.yml selon vos besoins
city-compare compare "Lyon" "Nantes" -p profiles/mon_profil.yml
```
