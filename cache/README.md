# Geocoding Cache

This directory stores cached geocoding results from Nominatim API.

## Purpose

- Avoids repeated API calls for the same city
- Respects Nominatim's rate limit (1 request per second)
- Enables offline testing with pre-cached data

## Format

Each file is named `{city_name}.json` and contains:

```json
{
  "lat": 45.75,
  "lon": 4.85,
  "display_name": "Lyon, Auvergne-Rhône-Alpes, France"
}
```

## Example Cities Included

The following French cities are pre-cached for quick testing:
- Paris
- Lyon
- Toulouse
- Marseille

You can add more cities by running the tool with network access, or by manually creating JSON files with the correct format.
