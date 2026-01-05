"""Tests for the scoring DSL."""

import pytest

from city_compare.scoring import DEFAULT_WEIGHTS, ScoringDSL, ScoringError, calculate_weighted_score


class TestScoringDSLParsing:
    """Test DSL parsing."""

    def test_parse_simple_rule(self):
        """Test parsing a simple scoring rule."""
        rules = """
        score = rent_m2 + 10
        """
        dsl = ScoringDSL(rules_text=rules)
        assert len(dsl.rules) == 1
        assert dsl.rules[0].name == "score"
        assert dsl.rules[0].expression == "rent_m2 + 10"

    def test_parse_with_comments(self):
        """Test parsing rules with comments."""
        rules = """
        # This is a comment
        rent_score = 100 - rent_m2  # inline comment
        score = rent_score
        """
        dsl = ScoringDSL(rules_text=rules)
        assert len(dsl.rules) == 2
        assert dsl.rules[0].comment == "inline comment"

    def test_parse_multiple_rules(self):
        """Test parsing multiple rules."""
        rules = """
        intermediate = rent_m2 * 2
        score = intermediate + avg_temp_c
        """
        dsl = ScoringDSL(rules_text=rules)
        assert len(dsl.rules) == 2

    def test_missing_score_raises_error(self):
        """Test that missing score variable raises error."""
        rules = """
        other = rent_m2 * 2
        """
        with pytest.raises(ScoringError, match="score"):
            ScoringDSL(rules_text=rules)

    def test_invalid_variable_name(self):
        """Test that invalid variable names raise error."""
        rules = """
        123invalid = 10
        score = 123invalid
        """
        with pytest.raises(ScoringError, match="invalide"):
            ScoringDSL(rules_text=rules)


class TestScoringDSLEvaluation:
    """Test DSL evaluation."""

    def test_evaluate_simple(self):
        """Test simple evaluation."""
        rules = "score = rent_m2 + avg_temp_c"
        dsl = ScoringDSL(rules_text=rules)

        score, variables = dsl.evaluate(
            rent_m2=10.0,
            avg_temp_c=15.0,
            rain_days=100,
            hot_days=20,
        )

        assert score == 25.0
        assert variables["rent_m2"] == 10.0
        assert variables["avg_temp_c"] == 15.0

    def test_evaluate_with_functions(self):
        """Test evaluation with built-in functions."""
        rules = """
        clamped = clamp(rent_m2, 5, 15)
        score = clamped
        """
        dsl = ScoringDSL(rules_text=rules)

        # Test clamp lower bound
        score, _ = dsl.evaluate(rent_m2=2.0, avg_temp_c=0, rain_days=0, hot_days=0)
        assert score == 5.0

        # Test clamp upper bound
        score, _ = dsl.evaluate(rent_m2=20.0, avg_temp_c=0, rain_days=0, hot_days=0)
        assert score == 15.0

        # Test within bounds
        score, _ = dsl.evaluate(rent_m2=10.0, avg_temp_c=0, rain_days=0, hot_days=0)
        assert score == 10.0

    def test_evaluate_intermediate_variables(self):
        """Test that intermediate variables are computed correctly."""
        rules = """
        double_rent = rent_m2 * 2
        triple_rent = double_rent + rent_m2
        score = triple_rent
        """
        dsl = ScoringDSL(rules_text=rules)

        score, variables = dsl.evaluate(
            rent_m2=10.0,
            avg_temp_c=0,
            rain_days=0,
            hot_days=0,
        )

        assert score == 30.0
        assert variables["double_rent"] == 20.0
        assert variables["triple_rent"] == 30.0

    def test_evaluate_min_max_abs(self):
        """Test min, max, and abs functions."""
        rules = """
        minimum = min(rent_m2, avg_temp_c)
        maximum = max(rent_m2, avg_temp_c)
        absolute = abs(avg_temp_c - 20)
        score = minimum + maximum + absolute
        """
        dsl = ScoringDSL(rules_text=rules)

        score, variables = dsl.evaluate(
            rent_m2=10.0,
            avg_temp_c=15.0,
            rain_days=0,
            hot_days=0,
        )

        assert variables["minimum"] == 10.0
        assert variables["maximum"] == 15.0
        assert variables["absolute"] == 5.0
        assert score == 30.0

    def test_unknown_variable_raises_error(self):
        """Test that unknown variables raise error."""
        rules = "score = unknown_var"
        dsl = ScoringDSL(rules_text=rules)

        with pytest.raises(ScoringError, match="inconnue"):
            dsl.evaluate(rent_m2=10.0, avg_temp_c=15.0, rain_days=100, hot_days=20)


class TestScoringExplanation:
    """Test score explanation generation."""

    def test_get_explanation(self):
        """Test explanation generation."""
        rules = """
        rent_score = 100 - rent_m2  # Loyer inversé
        score = rent_score  # Score final
        """
        dsl = ScoringDSL(rules_text=rules)

        _, variables = dsl.evaluate(
            rent_m2=10.0,
            avg_temp_c=15.0,
            rain_days=100,
            hot_days=20,
        )

        explanation = dsl.get_explanation(variables)

        assert "rent_m2" in explanation
        assert "rent_score" in explanation
        assert "score" in explanation
        assert "90.00" in explanation  # 100 - 10


class TestWeightedScoring:
    """Test weighted scoring function."""

    def test_default_weights(self):
        """Test that default weights sum to 1.0."""
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_calculate_weighted_score_basic(self):
        """Test basic weighted score calculation."""
        score, details = calculate_weighted_score(
            rent_m2=12.0,
            sunshine_hours=2000.0,
            avg_temp=15.0,  # Température idéale
            precipitation=800.0,
        )

        # Score devrait être entre 0 et 100
        assert 0 <= score <= 100
        assert "final_score" in details
        assert details["final_score"] == score

    def test_calculate_weighted_score_with_custom_weights(self):
        """Test with custom weights prioritizing sun."""
        weights = {
            "rent_m2": 0.10,
            "sunshine_hours": 0.60,  # Priorité soleil
            "avg_temp": 0.15,
            "precipitation": 0.10,
            "air_quality": 0.05,
        }

        # Ville ensoleillée
        score_sunny, _ = calculate_weighted_score(
            rent_m2=15.0,
            sunshine_hours=2800.0,  # Très ensoleillé
            avg_temp=16.0,
            precipitation=600.0,
            weights=weights,
        )

        # Ville moins ensoleillée
        score_cloudy, _ = calculate_weighted_score(
            rent_m2=15.0,
            sunshine_hours=1600.0,  # Peu ensoleillé
            avg_temp=16.0,
            precipitation=600.0,
            weights=weights,
        )

        # Avec poids soleil à 60%, la ville ensoleillée devrait scorer plus haut
        assert score_sunny > score_cloudy

    def test_calculate_weighted_score_with_air_quality(self):
        """Test scoring with air quality data."""
        score_good, details = calculate_weighted_score(
            rent_m2=12.0,
            sunshine_hours=2000.0,
            avg_temp=15.0,
            precipitation=800.0,
            air_quality=25.0,  # Bonne qualité
        )

        score_bad, _ = calculate_weighted_score(
            rent_m2=12.0,
            sunshine_hours=2000.0,
            avg_temp=15.0,
            precipitation=800.0,
            air_quality=80.0,  # Mauvaise qualité
        )

        assert score_good > score_bad
        assert details["air_score"] == 75.0  # 100 - 25

    def test_calculate_weighted_score_ideal_temp(self):
        """Test scoring with custom ideal temperature."""
        # Méditerranéen préfère 18°C
        score_18, _ = calculate_weighted_score(
            rent_m2=12.0,
            sunshine_hours=2500.0,
            avg_temp=18.0,
            precipitation=600.0,
            ideal_temp=18.0,
        )

        # Nord préfère 12°C
        score_12, _ = calculate_weighted_score(
            rent_m2=12.0,
            sunshine_hours=2500.0,
            avg_temp=12.0,
            precipitation=600.0,
            ideal_temp=18.0,  # Même idéal
        )

        # 18°C devrait scorer mieux si l'idéal est 18°C
        assert score_18 > score_12


class TestConditionalSyntax:
    """Test conditional syntax (condition => action)."""

    def test_parse_conditional_rules(self):
        """Test parsing conditional rules."""
        rules = """
        # Bonus for low rent
        rent_m2 < 10 => bonus(15)
        rent_m2 >= 10 and rent_m2 < 15 => bonus(5)
        """
        dsl = ScoringDSL(rules_text=rules)
        assert len(dsl.conditional_rules) == 2
        assert dsl._use_conditional_syntax is True

    def test_evaluate_conditional_bonus(self):
        """Test evaluating bonus conditions."""
        rules = """
        rent_m2 < 10 => bonus(15)
        sunshine_hours > 2500 => bonus(10)
        """
        dsl = ScoringDSL(rules_text=rules)

        # Low rent, high sun
        adjustment, vars = dsl.evaluate(
            rent_m2=8.0,
            avg_temp_c=15.0,
            rain_days=100,
            hot_days=20,
            sunshine_hours=2700.0,
        )

        assert adjustment == 25.0  # 15 + 10
        assert vars["total_bonus"] == 25.0
        assert vars["total_penalty"] == 0.0

    def test_evaluate_conditional_penalty(self):
        """Test evaluating penalty conditions."""
        rules = """
        rent_m2 > 20 => penalty(10)
        aqi > 50 => penalty(5)
        """
        dsl = ScoringDSL(rules_text=rules)

        # High rent, bad air
        adjustment, vars = dsl.evaluate(
            rent_m2=25.0,
            avg_temp_c=15.0,
            rain_days=100,
            hot_days=20,
            aqi=60.0,
        )

        assert adjustment == -15.0  # -10 - 5
        assert vars["total_penalty"] == 15.0

    def test_evaluate_conditional_mixed(self):
        """Test evaluating mixed bonus/penalty."""
        rules = """
        sunshine_hours > 2500 => bonus(10)
        rent_m2 > 20 => penalty(5)
        """
        dsl = ScoringDSL(rules_text=rules)

        adjustment, vars = dsl.evaluate(
            rent_m2=22.0,
            avg_temp_c=15.0,
            rain_days=100,
            hot_days=20,
            sunshine_hours=2700.0,
        )

        assert adjustment == 5.0  # 10 - 5
        assert vars["total_bonus"] == 10.0
        assert vars["total_penalty"] == 5.0

    def test_conditional_with_and_operator(self):
        """Test conditional rules with 'and' operator."""
        rules = """
        sunshine_hours > 2500 and avg_temp > 14 => bonus(20)
        """
        dsl = ScoringDSL(rules_text=rules)

        # Both conditions true
        adjustment, _ = dsl.evaluate(
            rent_m2=15.0,
            avg_temp_c=16.0,
            rain_days=100,
            hot_days=20,
            sunshine_hours=2700.0,
        )
        assert adjustment == 20.0

        # Only one condition true
        adjustment, _ = dsl.evaluate(
            rent_m2=15.0,
            avg_temp_c=12.0,  # Below 14
            rain_days=100,
            hot_days=20,
            sunshine_hours=2700.0,
        )
        assert adjustment == 0.0

    def test_parse_box_drawing_comments(self):
        """Test that box-drawing characters are skipped."""
        rules = """
        # ┌─────────────────────────────────────────┐
        # │  💰 RÈGLES LOYER                         │
        # └─────────────────────────────────────────┘
        rent_m2 < 10 => bonus(15)
        """
        dsl = ScoringDSL(rules_text=rules)
        assert len(dsl.conditional_rules) == 1

    def test_conditional_explanation(self):
        """Test explanation generation for conditional rules."""
        rules = """
        rent_m2 < 10 => bonus(15)
        sunshine_hours > 2500 => bonus(10)
        """
        dsl = ScoringDSL(rules_text=rules)

        adjustment, vars = dsl.evaluate(
            rent_m2=8.0,
            avg_temp_c=15.0,
            rain_days=100,
            hot_days=20,
            sunshine_hours=2700.0,
        )

        explanation = dsl.get_explanation(vars)
        assert "bonus" in explanation.lower()
        assert "+25" in explanation
