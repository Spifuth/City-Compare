#!/usr/bin/env python3
"""
City Compare CLI - Compare two French cities
"""
import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
import yaml

# Thresholds for metrics
RAIN_THRESHOLD_MM = 1.0  # Minimum precipitation to count as a rainy day
HOT_DAY_THRESHOLD_CELSIUS = 30.0  # Temperature threshold for counting hot days


class GeocodingCache:
    """Cache for Nominatim geocoding results with rate limiting"""
    
    def __init__(self, cache_dir="cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.last_request_time = 0
        self.rate_limit = 1.0  # 1 second between requests
    
    def get_coordinates(self, city_name):
        """Get coordinates for a city, using cache if available"""
        cache_file = self.cache_dir / f"{city_name}.json"
        
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        
        # Query Nominatim
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': city_name,
            'country': 'France',
            'format': 'json',
            'limit': 1
        }
        headers = {
            'User-Agent': 'CityCompare/1.0'
        }
        
        self.last_request_time = time.time()
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        results = response.json()
        if not results:
            raise ValueError(f"City not found: {city_name}")
        
        data = {
            'lat': float(results[0]['lat']),
            'lon': float(results[0]['lon']),
            'display_name': results[0]['display_name']
        }
        
        # Cache the result
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return data


class WeatherFetcher:
    """Fetch weather data from Open-Meteo API"""
    
    def __init__(self, use_demo_data=False):
        self.use_demo_data = use_demo_data
    
    def get_yearly_weather(self, lat, lon):
        """Get 12 months of weather data"""
        if self.use_demo_data:
            return self._get_demo_weather(lat, lon)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            'latitude': lat,
            'longitude': lon,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'daily': 'temperature_2m_mean,precipitation_sum,temperature_2m_max',
            'timezone': 'Europe/Paris'
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    def _get_demo_weather(self, lat, lon):
        """Generate demo weather data for testing"""
        # Constants for seasonal calculations
        DAYS_IN_YEAR = 365
        SEASONAL_VARIATION_AMPLITUDE = 8
        SUMMER_SOLSTICE_DAY = 180
        
        # Generate realistic weather data based on latitude
        # Southern France: warmer, less rain
        # Northern France: cooler, more rain
        base_temp = 15.0 - (lat - 45.0) * 0.5
        
        temps = []
        precips = []
        temp_maxs = []
        
        for i in range(DAYS_IN_YEAR):
            # Seasonal variation
            day_of_year = i
            seasonal_factor = -SEASONAL_VARIATION_AMPLITUDE * (1 - 2 * abs((day_of_year - SUMMER_SOLSTICE_DAY) / DAYS_IN_YEAR))
            
            daily_temp = base_temp + seasonal_factor + random.uniform(-3, 3)
            temps.append(round(daily_temp, 1))
            
            daily_max = daily_temp + random.uniform(3, 8)
            temp_maxs.append(round(daily_max, 1))
            
            # Rain probability varies by latitude
            rain_prob = 0.25 + (lat - 43.0) * 0.02
            if random.random() < rain_prob:
                precips.append(round(random.uniform(1, 20), 1))
            else:
                precips.append(0)
        
        return {
            'daily': {
                'temperature_2m_mean': temps,
                'precipitation_sum': precips,
                'temperature_2m_max': temp_maxs
            }
        }


class RentDataLoader:
    """Load rent data from CSV file"""
    
    def __init__(self, csv_path):
        self.csv_path = Path(csv_path)
        self.rent_data = {}
        if self.csv_path.exists():
            self._load_data()
    
    def _load_data(self):
        """Load rent data from CSV"""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) > 1:
                # Skip header
                for line in lines[1:]:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        city = parts[0].strip()
                        try:
                            rent = float(parts[1].strip())
                            self.rent_data[city.lower()] = rent
                        except ValueError:
                            continue
    
    def get_rent(self, city_name):
        """Get rent price for a city"""
        return self.rent_data.get(city_name.lower(), None)


class MetricsCalculator:
    """Calculate metrics from weather data"""
    
    @staticmethod
    def calculate_metrics(weather_data):
        """Calculate all metrics from weather data"""
        daily = weather_data.get('daily', {})
        temps = daily.get('temperature_2m_mean', [])
        precip = daily.get('precipitation_sum', [])
        temp_max = daily.get('temperature_2m_max', [])
        
        # Average temperature
        valid_temps = [t for t in temps if t is not None]
        avg_temp = sum(valid_temps) / len(valid_temps) if valid_temps else 0
        
        # Number of rainy days (precipitation > threshold)
        rainy_days = sum(1 for p in precip if p is not None and p > RAIN_THRESHOLD_MM)
        
        # Number of days above hot day threshold
        hot_days = sum(1 for t in temp_max if t is not None and t > HOT_DAY_THRESHOLD_CELSIUS)
        
        return {
            'avg_temp': round(avg_temp, 1),
            'rainy_days': rainy_days,
            'hot_days': hot_days
        }


class ScoringRulesParser:
    """Parse and evaluate scoring rules DSL"""
    
    def __init__(self, rules_path):
        self.rules_path = Path(rules_path)
        self.rules = []
        if self.rules_path.exists():
            self._load_rules()
    
    def _load_rules(self):
        """Load scoring rules from file"""
        with open(self.rules_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.rules.append(line)
    
    def evaluate(self, metrics, preferences):
        """Evaluate rules and calculate score"""
        score = 0
        explanations = []
        
        for rule in self.rules:
            rule_score, explanation = self._evaluate_rule(rule, metrics, preferences)
            score += rule_score
            if explanation:
                explanations.append(explanation)
        
        return score, explanations
    
    def _evaluate_rule(self, rule, metrics, preferences):
        """Evaluate a single rule"""
        # Simple DSL: metric operator value -> score
        # Example: avg_temp > 15 -> +10
        # Example: rainy_days < 100 -> +5
        # Example: hot_days < 20 -> +5
        # Example: rent < 15 -> +20
        
        try:
            if '->' not in rule:
                return 0, None
            
            condition, score_str = rule.split('->', 1)
            condition = condition.strip()
            score_value = int(score_str.strip())
            
            # Parse condition
            for op in ['<=', '>=', '<', '>', '==']:
                if op in condition:
                    parts = condition.split(op, 1)
                    if len(parts) == 2:
                        metric_name = parts[0].strip()
                        threshold = float(parts[1].strip())
                        
                        if metric_name not in metrics:
                            return 0, None
                        
                        metric_value = metrics[metric_name]
                        
                        # Evaluate condition
                        result = False
                        if op == '<':
                            result = metric_value < threshold
                        elif op == '>':
                            result = metric_value > threshold
                        elif op == '<=':
                            result = metric_value <= threshold
                        elif op == '>=':
                            result = metric_value >= threshold
                        elif op == '==':
                            result = metric_value == threshold
                        
                        if result:
                            explanation = f"{metric_name} {op} {threshold}: {metric_value} → {score_value:+d} points"
                            return score_value, explanation
                        
                        break
            
            return 0, None
        except Exception:
            return 0, None


class ReportGenerator:
    """Generate markdown report"""
    
    @staticmethod
    def generate(city1_data, city2_data, output_path="report.md"):
        """Generate comparison report"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# City Comparison Report\n\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Cities\n\n")
            f.write(f"- **City 1**: {city1_data['name']}\n")
            f.write(f"- **City 2**: {city2_data['name']}\n\n")
            
            f.write("## Metrics Comparison\n\n")
            f.write("| Metric | City 1 | City 2 |\n")
            f.write("|--------|--------|--------|\n")
            
            metrics1 = city1_data['metrics']
            metrics2 = city2_data['metrics']
            
            f.write(f"| Rent (€/m²) | {metrics1.get('rent', 'N/A')} | {metrics2.get('rent', 'N/A')} |\n")
            f.write(f"| Avg Temperature (°C) | {metrics1['avg_temp']} | {metrics2['avg_temp']} |\n")
            f.write(f"| Rainy Days | {metrics1['rainy_days']} | {metrics2['rainy_days']} |\n")
            f.write(f"| Hot Days (>30°C) | {metrics1['hot_days']} | {metrics2['hot_days']} |\n\n")
            
            f.write("## Scores\n\n")
            f.write(f"- **City 1 Score**: {city1_data['score']}\n")
            f.write(f"- **City 2 Score**: {city2_data['score']}\n\n")
            
            if city1_data['score'] > city2_data['score']:
                winner = city1_data['name']
            elif city2_data['score'] > city1_data['score']:
                winner = city2_data['name']
            else:
                winner = "Tie"
            
            f.write(f"**Winner**: {winner}\n\n")
            
            f.write("## Score Explanations\n\n")
            f.write(f"### {city1_data['name']}\n\n")
            for exp in city1_data['explanations']:
                f.write(f"- {exp}\n")
            f.write("\n")
            
            f.write(f"### {city2_data['name']}\n\n")
            for exp in city2_data['explanations']:
                f.write(f"- {exp}\n")


class SummaryGenerator:
    """Generate JSON summary"""
    
    @staticmethod
    def generate(city1_data, city2_data, output_path="summary.json"):
        """Generate JSON summary"""
        summary = {
            'generated_at': datetime.now().isoformat(),
            'cities': [
                {
                    'name': city1_data['name'],
                    'location': city1_data['location'],
                    'metrics': city1_data['metrics'],
                    'score': city1_data['score'],
                    'explanations': city1_data['explanations']
                },
                {
                    'name': city2_data['name'],
                    'location': city2_data['location'],
                    'metrics': city2_data['metrics'],
                    'score': city2_data['score'],
                    'explanations': city2_data['explanations']
                }
            ]
        }
        
        if city1_data['score'] > city2_data['score']:
            summary['winner'] = city1_data['name']
        elif city2_data['score'] > city1_data['score']:
            summary['winner'] = city2_data['name']
        else:
            summary['winner'] = 'tie'
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)


class CityCompare:
    """Main city comparison application"""
    
    def __init__(self, profile_path="profile.yml", rules_path="scoring.rules", rent_csv="rent_data.csv", use_demo_data=False):
        self.profile = self._load_profile(profile_path)
        self.rules_parser = ScoringRulesParser(rules_path)
        self.rent_loader = RentDataLoader(rent_csv)
        self.geocoding_cache = GeocodingCache()
        self.weather_fetcher = WeatherFetcher(use_demo_data=use_demo_data)
    
    def _load_profile(self, profile_path):
        """Load user profile"""
        if not Path(profile_path).exists():
            return {}
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def compare(self, city1_name, city2_name):
        """Compare two cities"""
        print(f"Comparing {city1_name} and {city2_name}...")
        
        # Get data for both cities
        city1_data = self._get_city_data(city1_name)
        city2_data = self._get_city_data(city2_name)
        
        # Generate outputs
        print("Generating report.md...")
        ReportGenerator.generate(city1_data, city2_data)
        
        print("Generating summary.json...")
        SummaryGenerator.generate(city1_data, city2_data)
        
        print("Done!")
    
    def _get_city_data(self, city_name):
        """Get all data for a city"""
        print(f"  Fetching data for {city_name}...")
        
        # Geocoding
        print(f"    - Geocoding...")
        coords = self.geocoding_cache.get_coordinates(city_name)
        
        # Weather data
        print(f"    - Weather data...")
        weather_data = self.weather_fetcher.get_yearly_weather(coords['lat'], coords['lon'])
        
        # Calculate metrics
        metrics = MetricsCalculator.calculate_metrics(weather_data)
        
        # Add rent data
        rent = self.rent_loader.get_rent(city_name)
        if rent is not None:
            metrics['rent'] = rent
        
        # Calculate score
        score, explanations = self.rules_parser.evaluate(metrics, self.profile)
        
        return {
            'name': city_name,
            'location': coords,
            'metrics': metrics,
            'score': score,
            'explanations': explanations
        }


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description='Compare two French cities')
    parser.add_argument('city1', help='First city name')
    parser.add_argument('city2', help='Second city name')
    parser.add_argument('--profile', default='profile.yml', help='Profile YAML file (default: profile.yml)')
    parser.add_argument('--rules', default='scoring.rules', help='Scoring rules file (default: scoring.rules)')
    parser.add_argument('--rent-csv', default='rent_data.csv', help='Rent data CSV file (default: rent_data.csv)')
    parser.add_argument('--demo', action='store_true', help='Use demo data (for testing without network access)')
    
    args = parser.parse_args()
    
    try:
        comparer = CityCompare(
            profile_path=args.profile,
            rules_path=args.rules,
            rent_csv=args.rent_csv,
            use_demo_data=args.demo
        )
        comparer.compare(args.city1, args.city2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
