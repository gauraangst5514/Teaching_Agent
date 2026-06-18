"""
Mathematics tool definitions for the Teacher Assistant agent system.

Uses SymPy to verify, solve, and simplify mathematical expressions,
and exports OpenAI-format tool definitions for the agentic loop.
"""

from typing import Any, Callable

import sympy
from sympy import sympify, solve, simplify, Eq
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)

# Parsing transformations for lenient input handling
_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def verify_equation(equation_str: str) -> str:
    """Verify whether a mathematical equation is correct.

    Accepts equations in the form ``LHS = RHS``.  If no ``=`` is present the
    expression is evaluated for truthiness.

    Args:
        equation_str: The equation string, e.g. ``"2*x + 3 = 7"`` or ``"sin(pi) = 0"``.

    Returns:
        A human-readable verification result.
    """
    try:
        equation_str = equation_str.strip()

        if "=" in equation_str and "==" not in equation_str:
            parts = equation_str.split("=", 1)
            lhs = parse_expr(parts[0].strip(), transformations=_TRANSFORMATIONS)
            rhs = parse_expr(parts[1].strip(), transformations=_TRANSFORMATIONS)

            diff = simplify(lhs - rhs)
            if diff == 0:
                return f"VERIFIED: The equation '{equation_str}' is correct. Both sides are equal."
            else:
                return (
                    f"INCORRECT: The equation '{equation_str}' is NOT correct. "
                    f"The difference (LHS - RHS) simplifies to: {diff}"
                )
        else:
            expr = parse_expr(equation_str, transformations=_TRANSFORMATIONS)
            simplified = simplify(expr)
            return f"Expression '{equation_str}' simplifies to: {simplified}"
    except Exception as e:
        return f"Error verifying equation '{equation_str}': {e}"


def solve_equation(equation_str: str) -> str:
    """Solve a mathematical equation for its unknowns.

    Accepts forms like ``"2*x + 3 = 7"`` (solves for *x*) or a plain
    expression assumed equal to zero.

    Args:
        equation_str: The equation to solve.

    Returns:
        Solution(s) as a string, or an error message.
    """
    try:
        equation_str = equation_str.strip()

        if "=" in equation_str and "==" not in equation_str:
            parts = equation_str.split("=", 1)
            lhs = parse_expr(parts[0].strip(), transformations=_TRANSFORMATIONS)
            rhs = parse_expr(parts[1].strip(), transformations=_TRANSFORMATIONS)
            equation = Eq(lhs, rhs)
        else:
            expr = parse_expr(equation_str, transformations=_TRANSFORMATIONS)
            equation = Eq(expr, 0)

        # Detect free symbols and solve
        symbols = list(equation.free_symbols)
        if not symbols:
            # No unknowns — just check truth
            result = simplify(equation)
            return f"No unknowns found. The equation evaluates to: {result}"

        solutions = solve(equation, symbols)

        if not solutions:
            return f"No solutions found for '{equation_str}'."

        if isinstance(solutions, dict):
            parts_out = [f"  {sym} = {val}" for sym, val in solutions.items()]
            return "Solutions:\n" + "\n".join(parts_out)
        elif isinstance(solutions, list):
            if len(symbols) == 1:
                sym = symbols[0]
                parts_out = [f"  {sym} = {sol}" for sol in solutions]
                return "Solutions:\n" + "\n".join(parts_out)
            else:
                return f"Solutions: {solutions}"
        else:
            return f"Solutions: {solutions}"
    except Exception as e:
        return f"Error solving equation '{equation_str}': {e}"


def simplify_expression(expr_str: str) -> str:
    """Simplify a mathematical expression.

    Args:
        expr_str: The expression to simplify, e.g. ``"(x**2 - 1)/(x - 1)"``.

    Returns:
        The simplified expression as a string, or an error message.
    """
    try:
        expr = parse_expr(expr_str.strip(), transformations=_TRANSFORMATIONS)
        simplified = simplify(expr)
        return f"Simplified: {simplified}"
    except Exception as e:
        return f"Error simplifying expression '{expr_str}': {e}"


# ---------------------------------------------------------------------------
# OpenAI-format tool definitions
# ---------------------------------------------------------------------------

def get_math_tools() -> list[dict[str, Any]]:
    """Return math tool definitions in OpenAI tool-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": "verify_equation",
                "description": (
                    "Verify whether a mathematical equation is correct. "
                    "Pass equations as 'LHS = RHS'. Returns verification result."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "equation_str": {
                            "type": "string",
                            "description": "The equation to verify, e.g. '2*x + 3 = 7'.",
                        }
                    },
                    "required": ["equation_str"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "solve_equation",
                "description": (
                    "Solve a mathematical equation for its unknowns. "
                    "Pass equations as 'LHS = RHS' or an expression equal to zero."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "equation_str": {
                            "type": "string",
                            "description": "The equation to solve, e.g. 'x**2 - 4 = 0'.",
                        }
                    },
                    "required": ["equation_str"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "simplify_expression",
                "description": (
                    "Simplify a mathematical expression using algebraic rules. "
                    "Returns the simplified form."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expr_str": {
                            "type": "string",
                            "description": "The expression to simplify, e.g. '(x**2 - 1)/(x - 1)'.",
                        }
                    },
                    "required": ["expr_str"],
                },
            },
        },
    ]


# ---------------------------------------------------------------------------
# Tool registry (name -> callable)
# ---------------------------------------------------------------------------

MATH_TOOLS: dict[str, Callable[..., str]] = {
    "verify_equation": verify_equation,
    "solve_equation": solve_equation,
    "simplify_expression": simplify_expression,
}
