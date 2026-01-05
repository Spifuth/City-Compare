"""Safe AST-based expression parser for scoring DSL."""

import ast
import operator
from collections.abc import Callable
from typing import Any


class SafeExpressionError(Exception):
    """Raised when expression parsing or evaluation fails."""

    pass


class SafeExpressionEvaluator:
    """
    Safe expression evaluator using Python's AST module.

    Only allows:
    - Numbers (int, float)
    - Variables from provided namespace
    - Basic arithmetic operators: +, -, *, /, unary -
    - Parentheses for grouping
    - Whitelisted function calls
    """

    # Allowed binary operators
    BINARY_OPS: dict[type, Callable[[Any, Any], float]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    # Allowed unary operators
    UNARY_OPS: dict[type, Callable[[Any], float]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def __init__(
        self,
        variables: dict[str, float],
        functions: dict[str, Callable[..., float]],
    ):
        """
        Initialize the evaluator.

        Args:
            variables: Dict of variable names to their values
            functions: Dict of function names to callable implementations
        """
        self.variables = variables
        self.functions = functions

    def evaluate(self, expression: str) -> float:
        """
        Safely evaluate a mathematical expression.

        Args:
            expression: The expression string to evaluate

        Returns:
            The computed float result

        Raises:
            SafeExpressionError: If the expression is invalid or uses forbidden constructs
        """
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            raise SafeExpressionError(f"Erreur de syntaxe: {e}") from e

        try:
            result = self._eval_node(tree.body)
            return float(result)
        except SafeExpressionError:
            raise
        except Exception as e:
            raise SafeExpressionError(f"Erreur d'évaluation: {e}") from e

    def _eval_node(self, node: ast.expr) -> float:
        """Recursively evaluate an AST node."""
        match node:
            case ast.Constant(value=value):
                # Numbers
                if isinstance(value, (int, float)):
                    return float(value)
                raise SafeExpressionError(f"Type de constante non autorisé: {type(value).__name__}")

            case ast.Name(id=name):
                # Variable lookup
                if name in self.variables:
                    return self.variables[name]
                if name in self.functions:
                    raise SafeExpressionError(
                        f"'{name}' est une fonction, pas une variable. Utilisez {name}(...)"
                    )
                raise SafeExpressionError(f"Variable inconnue: '{name}'")

            case ast.BinOp(left=left, op=bin_op, right=right):
                # Binary operations: +, -, *, /
                bin_op_type = type(bin_op)
                if bin_op_type not in self.BINARY_OPS:
                    raise SafeExpressionError(
                        f"Opérateur binaire non autorisé: {bin_op_type.__name__}"
                    )
                left_val = self._eval_node(left)
                right_val = self._eval_node(right)

                # Check for division by zero
                if bin_op_type == ast.Div and right_val == 0:
                    raise SafeExpressionError("Division par zéro")

                return self.BINARY_OPS[bin_op_type](left_val, right_val)

            case ast.UnaryOp(op=unary_op, operand=operand):
                # Unary operations: +x, -x
                unary_op_type = type(unary_op)
                if unary_op_type not in self.UNARY_OPS:
                    raise SafeExpressionError(
                        f"Opérateur unaire non autorisé: {unary_op_type.__name__}"
                    )
                return self.UNARY_OPS[unary_op_type](self._eval_node(operand))

            case ast.Call(func=ast.Name(id=func_name), args=args, keywords=keywords):
                # Function calls
                if keywords:
                    raise SafeExpressionError(
                        "Arguments nommés non autorisés dans les appels de fonction"
                    )
                if func_name not in self.functions:
                    available = ", ".join(self.functions.keys())
                    raise SafeExpressionError(
                        f"Fonction inconnue: '{func_name}'. Fonctions disponibles: {available}"
                    )

                # Evaluate arguments
                evaluated_args = [self._eval_node(arg) for arg in args]

                try:
                    return float(self.functions[func_name](*evaluated_args))
                except TypeError as e:
                    raise SafeExpressionError(
                        f"Erreur d'appel de fonction '{func_name}': {e}"
                    ) from e

            case _:
                raise SafeExpressionError(f"Construction non autorisée: {type(node).__name__}")


def safe_eval(
    expression: str,
    variables: dict[str, float],
    functions: dict[str, Callable[..., float]] | None = None,
) -> float:
    """
    Convenience function for safe expression evaluation.

    Args:
        expression: Mathematical expression to evaluate
        variables: Variable name to value mapping
        functions: Optional function name to callable mapping

    Returns:
        The computed result as a float
    """
    if functions is None:
        functions = {}

    evaluator = SafeExpressionEvaluator(variables, functions)
    return evaluator.evaluate(expression)
