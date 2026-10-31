"""Safe arithmetic evaluator (AST based; no eval())."""
import ast
import math
import operator
import re

from .base import ToolError

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UN = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log,
          "log10": math.log10, "exp": math.exp, "abs": abs, "round": round, "floor": math.floor,
          "ceil": math.ceil, "radians": math.radians, "degrees": math.degrees}
_CONST = {"pi": math.pi, "e": math.e}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        a, b = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(b) > 1000 or abs(a) > 1e9):
            raise ToolError("That exponent is too large.")
        return _BIN[type(node.op)](a, b)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        return _UN[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONST:
        return _CONST[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and not node.keywords:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ToolError("Unsupported expression.")


def calculate(expression: str) -> str:
    expr = (expression or "").strip()
    if not expr or len(expr) > 200:
        raise ToolError("Give me a short arithmetic expression.")
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/")
    expr = re.sub(r"(?<=[\d)])\s*x\s*(?=[\d(])", "*", expr)  # "3 x 4" -> "3*4"
    try:
        value = _eval(ast.parse(expr, mode="eval"))
    except ToolError:
        raise
    except ZeroDivisionError:
        raise ToolError("Division by zero.")
    except (SyntaxError, ValueError, TypeError, OverflowError) as e:
        raise ToolError(f"I couldn't evaluate that: {e}")
    if isinstance(value, float):
        value = int(value) if value.is_integer() and abs(value) < 1e15 else float(f"{value:.10g}")
    return f"{expression.strip()} = {value}"
