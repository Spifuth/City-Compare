# Usage Examples

This document provides practical examples of using the City Compare CLI.

## Basic Comparison

Compare two cities using default configuration:

```bash
python city_compare.py Lyon Toulouse
```

## Using Demo Mode

For testing without network access (uses simulated weather data):

```bash
python city_compare.py Lyon Toulouse --demo
```

## Custom Configuration

Use custom configuration files:

```bash
python city_compare.py Paris Marseille \
  --profile my_profile.yml \
  --rules custom_scoring.rules \
  --rent-csv my_rent_data.csv
```

## Comparing Different City Pairs

```bash
# Compare major cities
python city_compare.py Paris Lyon --demo
python city_compare.py Marseille Toulouse --demo
python city_compare.py Lyon Bordeaux --demo
```

## Understanding the Output

After running a comparison, you'll get two output files:

### 1. report.md

A human-readable markdown report with:
- Metrics comparison table
- Scores for each city
- Winner declaration
- Detailed score explanations

Example excerpt:
```markdown
| Metric | City 1 | City 2 |
|--------|--------|--------|
| Rent (€/m²) | 16.2 | 13.9 |
| Avg Temperature (°C) | 10.6 | 11.6 |
| Rainy Days | 106 | 95 |
| Hot Days (>30°C) | 0 | 0 |
```

### 2. summary.json

A structured JSON file with all data:
```json
{
  "generated_at": "2026-01-04T20:11:31.131388",
  "cities": [
    {
      "name": "Lyon",
      "metrics": { ... },
      "score": 25,
      "explanations": [ ... ]
    },
    { ... }
  ],
  "winner": "Toulouse"
}
```

## Customizing Scoring Rules

Edit `scoring.rules` to change how cities are scored:

```
# Prefer cheaper rent
rent < 12 -> 30
rent < 15 -> 20
rent >= 25 -> -15

# Prefer warmer climate
avg_temp > 16 -> 20
avg_temp > 13 -> 10

# Prefer less rain
rainy_days < 70 -> 20
rainy_days < 90 -> 15
```

## Adding New Cities

### Method 1: Add to rent_data.csv

```csv
city,rent_per_m2
NewCity,12.5
```

### Method 2: Run with network access

The first time you compare a city, its geocoding data will be cached:
```bash
python city_compare.py NewCity Lyon
```

The geocoding result is saved to `cache/NewCity.json` for future use.

## Profile Configuration

Create a custom profile to express your preferences:

```yaml
# my_profile.yml
preferences:
  climate: warm       # Options: warm, moderate, cold
  max_rent: 18        # Maximum acceptable rent
  prefer_dry: true    # Prefer cities with less rain
  prefer_calm: false  # Prefer cities with fewer hot days
```

Note: The profile is loaded by the application but not currently used in the default scoring. You can extend the DSL to utilize these preferences.

## Tips

1. **Cache Management**: Cached geocoding results are stored in `cache/`. Delete files to refresh data.

2. **Network Issues**: Use `--demo` mode if you have network connectivity issues or for quick testing.

3. **Batch Comparisons**: Create a shell script to compare multiple cities:
   ```bash
   #!/bin/bash
   for city in Lyon Marseille Toulouse; do
     python city_compare.py Paris "$city" --demo
     mv report.md "report_Paris_vs_${city}.md"
     mv summary.json "summary_Paris_vs_${city}.json"
   done
   ```

4. **Rent Data**: Update `rent_data.csv` with real data from data.gouv.fr for accurate comparisons.
