"""Atomic weights and a small formula parser (``NiSO4.6H2O`` -> element mass fractions)."""
from __future__ import annotations

import re

# IUPAC standard atomic weights (abridged, conventional values), g/mol.
ATOMIC_WEIGHTS: dict[str, float] = {
    "H": 1.008, "Li": 6.94, "B": 10.81, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998,
    "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.085, "P": 30.974, "S": 32.06, "Cl": 35.45,
    "K": 39.098, "Ca": 40.078, "Ti": 47.867, "V": 50.942, "Cr": 51.996, "Mn": 54.938, "Fe": 55.845,
    "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38, "Ga": 69.723, "Ge": 72.630, "As": 74.922,
    "Se": 78.971, "Y": 88.906, "Zr": 91.224, "Nb": 92.906, "Mo": 95.95, "Ag": 107.868, "Sn": 118.71,
    "Sb": 121.76, "Ba": 137.327, "La": 138.905, "Ce": 140.116, "Pr": 140.908, "Nd": 144.242,
    "Sm": 150.36, "Eu": 151.964, "Gd": 157.25, "Tb": 158.925, "Dy": 162.500, "Ho": 164.930,
    "Er": 167.259, "Tm": 168.934, "Yb": 173.045, "Lu": 174.967, "W": 183.84, "Pt": 195.084,
    "Au": 196.967, "Pb": 207.2,
}

_TOKEN = re.compile(r"([A-Z][a-z]?|\(|\)|\d+(?:\.\d+)?)")


def _parse(formula: str) -> dict[str, float]:
    tokens = _TOKEN.findall(formula)
    if "".join(tokens) != formula:
        raise ValueError(f"cannot parse formula {formula!r}")
    stack: list[dict[str, float]] = [{}]
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "(":
            stack.append({})
        elif t == ")":
            group = stack.pop()
            mult = 1.0
            if i + 1 < len(tokens) and tokens[i + 1][0].isdigit():
                mult = float(tokens[i + 1])
                i += 1
            for el, n in group.items():
                stack[-1][el] = stack[-1].get(el, 0) + n * mult
        elif t[0].isdigit():
            raise ValueError(f"unexpected number in {formula!r}")
        else:
            if t not in ATOMIC_WEIGHTS:
                raise ValueError(f"unknown element {t!r} in {formula!r}")
            n = 1.0
            if i + 1 < len(tokens) and tokens[i + 1][0].isdigit():
                n = float(tokens[i + 1])
                i += 1
            stack[-1][t] = stack[-1].get(t, 0) + n
        i += 1
    if len(stack) != 1:
        raise ValueError(f"unbalanced parentheses in {formula!r}")
    return stack[0]


def composition(formula: str) -> dict[str, float]:
    """Element counts of a formula, hydrates with ``.`` or ``·`` supported; phase tags dropped."""
    f = re.sub(r"\((aq|s|l|g)\)$", "", formula.strip()).replace("·", ".")
    total: dict[str, float] = {}
    for part in f.split("."):
        m = re.match(r"^(\d+(?:\.\d+)?)(.*)$", part)
        mult, body = (float(m.group(1)), m.group(2)) if m else (1.0, part)
        for el, n in _parse(body).items():
            total[el] = total.get(el, 0) + n * mult
    return total


def molar_mass(formula: str) -> float:
    return sum(ATOMIC_WEIGHTS[el] * n for el, n in composition(formula).items())


def mass_fractions(formula: str) -> dict[str, float]:
    comp = composition(formula)
    mm = molar_mass(formula)
    return {el: ATOMIC_WEIGHTS[el] * n / mm for el, n in comp.items()}
