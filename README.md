# City-Compare
city-compare: CLI qui compare 2 villes FR et sort report.md + summary.json. Entrées: 2 noms de villes + profile.yml + scoring.rules (mini DSL). Données: géocode Nominatim (cache/1reqs), météo 12 mois Open-Meteo, loyers via CSV data.gouv (import manuel). Métriques: rent €/m², temp moy, nb jours pluie, nb jours >30°C. DSL calcule score et l’explique.
