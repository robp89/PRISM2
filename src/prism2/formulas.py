"""Safe arithmetic formulas shared by recipes, surrogates and the XYCLE export.

Recipes are written in the subset XYCLE's Parameter Import accepts: numbers, names,
``+ - * /``, parentheses. ``**`` with a small integer exponent is accepted here and
expanded to repeated multiplication on export. No function calls, no attributes.
"""
from __future__ import annotations

import ast
import math
import operator as op
from functools import lru_cache
from graphlib import CycleError, TopologicalSorter

_BIN = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow}
_UN = {ast.USub: op.neg, ast.UAdd: op.pos}


class FormulaError(ValueError):
    pass


def parse(expr: str) -> ast.Expression:
    return _parse_cached(str(expr))


@lru_cache(maxsize=4096)
def _parse_cached(expr: str) -> ast.Expression:
    try:
        tree = ast.parse(str(expr), mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"syntax error in formula {expr!r}: {e.msg}") from None
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load, ast.Name, ast.operator, ast.unaryop)):
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            continue
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            if isinstance(node.op, ast.Pow) and not (
                isinstance(node.right, ast.Constant) and isinstance(node.right.value, int) and 0 <= node.right.value <= 4
            ):
                raise FormulaError(f"only small integer powers (0 to 4) are allowed in {expr!r}")
            continue
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
            continue
        raise FormulaError(f"unsupported element {type(node).__name__} in formula {expr!r}")
    return tree


def names(expr: str) -> set[str]:
    return {n.id for n in ast.walk(parse(expr)) if isinstance(n, ast.Name)}


def evaluate(expr: str, env: dict[str, float]) -> float:
    tree = parse(expr)

    def ev(n: ast.AST) -> float:
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise FormulaError(f"unknown name {n.id!r} in formula {expr!r}")
            return float(env[n.id])
        if isinstance(n, ast.BinOp):
            return _BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp):
            return _UN[type(n.op)](ev(n.operand))
        raise FormulaError(f"unsupported node in {expr!r}")

    v = ev(tree)
    if not math.isfinite(v):
        raise FormulaError(f"formula {expr!r} is not finite")
    return v


def to_xycle(expr: str) -> str:
    """Rewrite to XYCLE syntax: names become ``{{name}}`` and powers are expanded."""
    tree = parse(expr)

    def w(n: ast.AST, parent_prec: int = 0) -> str:
        if isinstance(n, ast.Expression):
            return w(n.body)
        if isinstance(n, ast.Constant):
            return repr(float(n.value)) if isinstance(n.value, float) else str(n.value)
        if isinstance(n, ast.Name):
            return "{{" + n.id + "}}"
        if isinstance(n, ast.UnaryOp):
            s = "-" + w(n.operand, 3)
            return f"({s})" if parent_prec >= 2 else s
        if isinstance(n, ast.BinOp):
            if isinstance(n.op, ast.Pow):
                k = n.right.value  # type: ignore[attr-defined]
                if k == 0:
                    return "1"
                base = w(n.left, 3)
                s = "*".join([base] * k)
                return f"({s})" if parent_prec >= 2 else s
            prec = 1 if isinstance(n.op, (ast.Add, ast.Sub)) else 2
            sym = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}[type(n.op)]
            left = w(n.left, prec)
            right = w(n.right, prec + (1 if isinstance(n.op, (ast.Sub, ast.Div)) else 0))
            s = f"{left} {sym} {right}" if prec == 1 else f"{left}{sym}{right}"
            return f"({s})" if parent_prec > prec else s
        raise FormulaError("unsupported")

    return w(tree)


def dependency_order(formulas: dict[str, str], known: set[str]) -> list[str]:
    """Order derived parameters so each comes after the names it uses."""
    return list(_order(tuple(formulas.items()), frozenset(known)))


@lru_cache(maxsize=256)
def _order(items: tuple, known: frozenset) -> tuple:
    formulas = dict(items)
    graph = {k: {n for n in names(v) if n in formulas} for k, v in formulas.items()}
    for k, v in formulas.items():
        missing = names(v) - set(formulas) - known
        if missing:
            raise FormulaError(f"{k}: unknown name(s) {sorted(missing)}")
    try:
        return tuple(TopologicalSorter(graph).static_order())
    except CycleError as e:
        raise FormulaError(f"circular formulas: {e.args[1]}") from None


def evaluate_all(formulas: dict[str, str], env: dict[str, float]) -> dict[str, float]:
    out = dict(env)
    for k in dependency_order(formulas, set(env)):
        out[k] = evaluate(formulas[k], out)
    return out
