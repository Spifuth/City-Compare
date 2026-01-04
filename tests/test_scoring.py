"""Tests for the scoring DSL."""

import pytest

from city_compare.scoring import ScoringDSL, ScoringError


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
