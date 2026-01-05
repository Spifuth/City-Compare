"""Tests for safe AST expression parser."""

import pytest

from city_compare.ast_parser import SafeExpressionError, SafeExpressionEvaluator, safe_eval


class TestSafeExpressionEvaluator:
    """Test the AST-based expression evaluator."""

    @pytest.fixture
    def evaluator(self) -> SafeExpressionEvaluator:
        """Create evaluator with sample variables and functions."""
        variables = {"x": 10.0, "y": 5.0, "z": 2.0}
        functions = {
            "clamp": lambda val, lo, hi: max(lo, min(hi, val)),
            "min": min,
            "max": max,
            "abs": abs,
        }
        return SafeExpressionEvaluator(variables, functions)

    def test_simple_number(self, evaluator: SafeExpressionEvaluator):
        """Test evaluating a simple number."""
        assert evaluator.evaluate("42") == 42.0
        assert evaluator.evaluate("3.14") == 3.14

    def test_variable_lookup(self, evaluator: SafeExpressionEvaluator):
        """Test variable lookup."""
        assert evaluator.evaluate("x") == 10.0
        assert evaluator.evaluate("y") == 5.0

    def test_binary_operations(self, evaluator: SafeExpressionEvaluator):
        """Test binary arithmetic operations."""
        assert evaluator.evaluate("x + y") == 15.0
        assert evaluator.evaluate("x - y") == 5.0
        assert evaluator.evaluate("x * y") == 50.0
        assert evaluator.evaluate("x / y") == 2.0

    def test_unary_operations(self, evaluator: SafeExpressionEvaluator):
        """Test unary operations."""
        assert evaluator.evaluate("-x") == -10.0
        assert evaluator.evaluate("+x") == 10.0
        assert evaluator.evaluate("--x") == 10.0

    def test_complex_expressions(self, evaluator: SafeExpressionEvaluator):
        """Test complex nested expressions."""
        assert evaluator.evaluate("(x + y) * z") == 30.0
        assert evaluator.evaluate("x + y * z") == 20.0
        assert evaluator.evaluate("(x - y) / z") == 2.5

    def test_function_calls(self, evaluator: SafeExpressionEvaluator):
        """Test whitelisted function calls."""
        assert evaluator.evaluate("abs(-5)") == 5.0
        assert evaluator.evaluate("min(x, y)") == 5.0
        assert evaluator.evaluate("max(x, y)") == 10.0
        assert evaluator.evaluate("clamp(15, 0, 10)") == 10.0
        assert evaluator.evaluate("clamp(-5, 0, 10)") == 0.0

    def test_nested_function_calls(self, evaluator: SafeExpressionEvaluator):
        """Test nested function calls."""
        assert evaluator.evaluate("abs(min(-x, -y))") == 10.0
        assert evaluator.evaluate("max(abs(-x), y)") == 10.0

    def test_function_with_expressions(self, evaluator: SafeExpressionEvaluator):
        """Test functions with expression arguments."""
        assert evaluator.evaluate("clamp(x + y, 0, 12)") == 12.0
        assert evaluator.evaluate("abs(x - y * 3)") == 5.0

    def test_division_by_zero(self, evaluator: SafeExpressionEvaluator):
        """Test division by zero raises error."""
        with pytest.raises(SafeExpressionError, match="Division par zéro"):
            evaluator.evaluate("x / 0")

    def test_unknown_variable(self, evaluator: SafeExpressionEvaluator):
        """Test unknown variable raises error."""
        with pytest.raises(SafeExpressionError, match="Variable inconnue"):
            evaluator.evaluate("unknown")

    def test_unknown_function(self, evaluator: SafeExpressionEvaluator):
        """Test unknown function raises error."""
        with pytest.raises(SafeExpressionError, match="Fonction inconnue"):
            evaluator.evaluate("sqrt(x)")

    def test_syntax_error(self, evaluator: SafeExpressionEvaluator):
        """Test syntax errors are caught."""
        with pytest.raises(SafeExpressionError, match="syntaxe"):
            evaluator.evaluate("x +")

    def test_forbidden_constructs(self, evaluator: SafeExpressionEvaluator):
        """Test that forbidden Python constructs are blocked."""
        # Lambda
        with pytest.raises(SafeExpressionError):
            evaluator.evaluate("lambda: x")

        # List comprehension
        with pytest.raises(SafeExpressionError):
            evaluator.evaluate("[i for i in range(10)]")

        # Attribute access
        with pytest.raises(SafeExpressionError):
            evaluator.evaluate("x.__class__")

        # Import
        with pytest.raises(SafeExpressionError):
            evaluator.evaluate("__import__('os')")

    def test_string_not_allowed(self, evaluator: SafeExpressionEvaluator):
        """Test that string constants are not allowed."""
        with pytest.raises(SafeExpressionError, match="non autorisé"):
            evaluator.evaluate("'hello'")

    def test_keyword_args_not_allowed(self, evaluator: SafeExpressionEvaluator):
        """Test that keyword arguments are blocked."""
        with pytest.raises(SafeExpressionError, match="Arguments nommés"):
            evaluator.evaluate("clamp(val=5, lo=0, hi=10)")


class TestSafeEvalConvenience:
    """Test the safe_eval convenience function."""

    def test_simple_eval(self):
        """Test simple evaluation."""
        result = safe_eval("a + b", {"a": 1.0, "b": 2.0})
        assert result == 3.0

    def test_with_functions(self):
        """Test evaluation with custom functions."""
        result = safe_eval(
            "double(x)",
            {"x": 5.0},
            {"double": lambda n: n * 2},
        )
        assert result == 10.0

    def test_no_functions(self):
        """Test evaluation without functions."""
        result = safe_eval("x * 2", {"x": 5.0})
        assert result == 10.0


class TestSecurityEdgeCases:
    """Test security edge cases to ensure no code execution."""

    @pytest.fixture
    def evaluator(self) -> SafeExpressionEvaluator:
        """Create minimal evaluator."""
        return SafeExpressionEvaluator({"x": 1.0}, {})

    def test_no_builtins_access(self, evaluator: SafeExpressionEvaluator):
        """Ensure builtins cannot be accessed."""
        dangerous = [
            "__builtins__",
            "__import__('os')",
            "eval('1+1')",
            "exec('x=1')",
            "open('file')",
            "globals()",
            "locals()",
            "dir()",
            "vars()",
            "type(x)",
            "getattr(x, '__class__')",
        ]
        for expr in dangerous:
            with pytest.raises(SafeExpressionError):
                evaluator.evaluate(expr)

    def test_no_dunder_access(self, evaluator: SafeExpressionEvaluator):
        """Ensure dunder attributes cannot be accessed."""
        with pytest.raises(SafeExpressionError):
            evaluator.evaluate("x.__class__.__mro__")

    def test_no_arbitrary_code(self, evaluator: SafeExpressionEvaluator):
        """Ensure arbitrary code cannot be executed."""
        with pytest.raises(SafeExpressionError):
            evaluator.evaluate("().__class__.__bases__[0].__subclasses__()")
