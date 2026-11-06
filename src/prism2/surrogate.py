"""Fitted models ("surrogates"): polynomial, neural network and Gaussian process, benchmarked on
identical held-out splits. Models are stored as JSON (weights and statistics), never pickled.

Decision rule (ANN-1, written before any result): for each target the family with the highest
held-out R² is chosen; if the polynomial is within 0.01 of the best it is preferred, because it can be
exported to XYCLE as a formula.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np
from scipy import stats

FAMILIES = ("polynomial", "ann", "gp")
POLY_PREFERENCE_MARGIN = 0.01


# ---- families -------------------------------------------------------------------------

def _poly_terms(n_in: int, degree: int) -> list[tuple[int, ...]]:
    terms: list[tuple[int, ...]] = [()]
    for d in range(1, degree + 1):
        terms += list(itertools.combinations_with_replacement(range(n_in), d))
    return terms


def _poly_design(Z: np.ndarray, terms) -> np.ndarray:
    return np.column_stack([np.prod(Z[:, list(t)], axis=1) if t else np.ones(len(Z)) for t in terms])


@dataclass
class Scaler:
    mu: np.ndarray
    sd: np.ndarray

    @classmethod
    def fit(cls, X):
        sd = X.std(axis=0)
        return cls(X.mean(axis=0), np.where(sd > 0, sd, 1.0))

    def __call__(self, X):
        return (X - self.mu) / self.sd


def fit_polynomial(X, y, degree=2, ridge=1e-6):
    sx = Scaler.fit(X)
    terms = _poly_terms(X.shape[1], degree)
    A = _poly_design(sx(X), terms)
    coef = np.linalg.solve(A.T @ A + ridge * np.eye(A.shape[1]), A.T @ y)
    return {"family": "polynomial", "degree": degree, "mu": sx.mu.tolist(), "sd": sx.sd.tolist(),
            "terms": [list(t) for t in terms], "coef": coef.tolist()}


def fit_ann(X, y, hidden=12, epochs=3000, lr=0.01, l2=1e-4, seed=0):
    rng = np.random.default_rng(seed)
    sx, my, sy = Scaler.fit(X), float(y.mean()), float(y.std() or 1.0)
    Z, t = sx(X), (y - my) / sy
    n_in = X.shape[1]
    W1 = rng.normal(0, 1 / math.sqrt(n_in), (n_in, hidden)); b1 = np.zeros(hidden)
    W2 = rng.normal(0, 1 / math.sqrt(hidden), hidden); b2 = 0.0
    params = [W1, b1, W2, np.array(b2)]
    m = [np.zeros_like(p) for p in params]; v = [np.zeros_like(p) for p in params]
    n = len(Z)
    for step in range(1, epochs + 1):
        H = np.tanh(Z @ params[0] + params[1])
        out = H @ params[2] + params[3]
        err = (out - t) / n
        gW2 = H.T @ err + l2 * params[2]
        gb2 = np.array(err.sum())
        dH = np.outer(err, params[2]) * (1 - H ** 2)
        gW1 = Z.T @ dH + l2 * params[0]
        gb1 = dH.sum(axis=0)
        for i, g in enumerate((gW1, gb1, gW2, gb2)):
            m[i] = 0.9 * m[i] + 0.1 * g
            v[i] = 0.999 * v[i] + 0.001 * g * g
            params[i] = params[i] - lr * (m[i] / (1 - 0.9 ** step)) / (np.sqrt(v[i] / (1 - 0.999 ** step)) + 1e-8)
    return {"family": "ann", "hidden": hidden, "activation": "tanh", "mu": sx.mu.tolist(), "sd": sx.sd.tolist(),
            "y_mu": my, "y_sd": sy, "W1": params[0].tolist(), "b1": params[1].tolist(), "W2": params[2].tolist(),
            "b2": float(params[3]), "epochs": epochs, "seed": seed}


def _rbf(A, B, ls):
    ls = np.broadcast_to(np.asarray(ls, float), (A.shape[1],))
    d2 = (((A[:, None, :] - B[None, :, :]) / ls) ** 2).sum(-1)
    return np.exp(-0.5 * d2)


def fit_gp(X, y, restarts=3, seed=0):
    """Gaussian process, RBF kernel with one length scale per input (ARD), hyperparameters by maximum
    marginal likelihood (L-BFGS-B from a few starts)."""
    from scipy.optimize import minimize

    sx, my, sy = Scaler.fit(X), float(y.mean()), float(y.std() or 1.0)
    Z, t = sx(X), (y - my) / sy
    d = Z.shape[1]

    def nlml(theta):
        ls, sf2, noise = np.exp(theta[:d]), np.exp(theta[d]), np.exp(theta[d + 1])
        K = sf2 * _rbf(Z, Z, ls) + (noise + 1e-8) * np.eye(len(Z))
        try:
            Lc = np.linalg.cholesky(K)
        except np.linalg.LinAlgError:
            return 1e10
        a = np.linalg.solve(Lc.T, np.linalg.solve(Lc, t))
        return float(0.5 * t @ a + np.log(np.diag(Lc)).sum())

    rng = np.random.default_rng(seed)
    bounds = [(np.log(0.05), np.log(50.0))] * d + [(np.log(0.05), np.log(20.0)), (np.log(1e-6), np.log(1.0))]
    best = None
    for r in range(restarts):
        x0 = np.concatenate([np.log(rng.uniform(0.7, 3.0, d)), [0.0], [np.log(1e-2)]]) if r else np.concatenate([np.full(d, np.log(1.5)), [0.0, np.log(1e-2)]])
        res = minimize(nlml, x0, method="L-BFGS-B", bounds=bounds)
        if best is None or res.fun < best.fun:
            best = res
    ls, sf2, noise = np.exp(best.x[:d]), float(np.exp(best.x[d])), float(np.exp(best.x[d + 1]))
    K = sf2 * _rbf(Z, Z, ls) + (noise + 1e-8) * np.eye(len(Z))
    alpha = np.linalg.solve(K, t)
    return {"family": "gp", "kernel": "rbf-ard", "length_scale": ls.tolist(), "signal_var": sf2, "noise": noise,
            "mu": sx.mu.tolist(), "sd": sx.sd.tolist(), "y_mu": my, "y_sd": sy, "Z": Z.tolist(), "alpha": alpha.tolist()}


FITTERS = {"polynomial": fit_polynomial, "ann": fit_ann, "gp": fit_gp}


def predict(model: dict, X: np.ndarray) -> np.ndarray:
    X = np.atleast_2d(np.asarray(X, float))
    Z = (X - np.array(model["mu"])) / np.array(model["sd"])
    fam = model["family"]
    if fam == "polynomial":
        return _poly_design(Z, [tuple(t) for t in model["terms"]]) @ np.array(model["coef"])
    if fam == "ann":
        H = np.tanh(Z @ np.array(model["W1"]) + np.array(model["b1"]))
        return (H @ np.array(model["W2"]) + model["b2"]) * model["y_sd"] + model["y_mu"]
    if fam == "gp":
        K = model.get("signal_var", 1.0) * _rbf(Z, np.array(model["Z"]), model["length_scale"])
        return (K @ np.array(model["alpha"])) * model["y_sd"] + model["y_mu"]
    raise ValueError(fam)


def polynomial_formula(model: dict, inputs: list[str]) -> str:
    """The polynomial as a PRISM/XYCLE formula of the raw input names."""
    zs = [f"(({n} - {mu!r}) / {sd!r})" for n, mu, sd in zip(inputs, model["mu"], model["sd"])]
    parts = []
    for t, c in zip(model["terms"], model["coef"]):
        if abs(c) < 1e-12:
            continue
        body = "*".join(zs[i] for i in t)
        parts.append(f"{c!r}" if not t else f"{c!r}*{body}")
    return " + ".join(parts).replace("+ -", "- ") or "0"


# ---- statistics ---------------------------------------------------------------------

def metrics(y, yhat) -> dict:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    res = y - yhat
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((res ** 2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    rel = np.abs(res) / np.maximum(np.abs(y), 1e-9) * 100
    try:
        sw_p = float(stats.shapiro(res).pvalue) if len(res) >= 3 and np.ptp(res) > 0 else float("nan")
    except Exception:  # noqa: BLE001
        sw_p = float("nan")
    return {"n": int(len(y)), "r2": r2, "rmse": float(np.sqrt((res ** 2).mean())), "mae": float(np.abs(res).mean()),
            "p90_rel_err_pct": float(np.percentile(rel, 90)), "normality_p": sw_p}


def split(n: int, holdout_fraction: float, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    idx = np.random.default_rng(seed).permutation(n)
    k = max(1, int(round(n * holdout_fraction)))
    return np.sort(idx[k:]), np.sort(idx[:k])


def kfold_r2(fam: str, X, y, k=5, seed=7, **kw) -> float:
    idx = np.random.default_rng(seed).permutation(len(X))
    folds = np.array_split(idx, k)
    preds = np.empty(len(X))
    for f in folds:
        tr = np.setdiff1d(idx, f)
        preds[f] = predict(FITTERS[fam](X[tr], y[tr], **kw), X[f])
    return metrics(y, preds)["r2"]


def sobol_indices(model: dict, lo: np.ndarray, hi: np.ndarray, n: int = 2048, seed: int = 3) -> dict:
    """First-order and total Sobol indices (Saltelli 2010 / Jansen estimators) inside the trained box."""
    d = len(lo)
    rng = np.random.default_rng(seed)
    A = lo + (hi - lo) * rng.random((n, d))
    B = lo + (hi - lo) * rng.random((n, d))
    fA, fB = predict(model, A), predict(model, B)
    var = float(np.var(np.concatenate([fA, fB])))
    S1, ST = [], []
    for i in range(d):
        ABi = A.copy(); ABi[:, i] = B[:, i]
        fABi = predict(model, ABi)
        S1.append(float(np.mean(fB * (fABi - fA)) / var) if var > 0 else 0.0)
        ST.append(float(0.5 * np.mean((fA - fABi) ** 2) / var) if var > 0 else 0.0)
    return {"first_order": S1, "total": ST}


def bootstrap_band(fam: str, X, y, Xq, n_boot=30, seed=11, **kw) -> tuple[np.ndarray, np.ndarray]:
    """5th and 95th percentile of predictions across bootstrap refits (model uncertainty)."""
    rng = np.random.default_rng(seed)
    preds = []
    for _ in range(n_boot):
        i = rng.integers(0, len(X), len(X))
        preds.append(predict(FITTERS[fam](X[i], y[i], **kw), Xq))
    P = np.array(preds)
    return np.percentile(P, 5, axis=0), np.percentile(P, 95, axis=0)


def choose(results: dict[str, dict]) -> str:
    """The decision rule (module docstring)."""
    best = max(results, key=lambda f: results[f]["holdout"]["r2"])
    if "polynomial" in results and results["polynomial"]["holdout"]["r2"] >= results[best]["holdout"]["r2"] - POLY_PREFERENCE_MARGIN:
        return "polynomial"
    return best
