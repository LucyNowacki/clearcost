"""Synthetic response modelling, chronological evaluation and bounded budgets."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear, minimize

from .metrics import regression_metrics

SEED = 20261015
CHANNELS = ("search", "social", "video")
DECAY = np.array([0.35, 0.55, 0.70])
HALF = np.array([14000.0, 20000.0, 26000.0])
TRUE_COEFFICIENTS = np.array([24000.0, 18000.0, 14000.0])
WEEKS, TRAIN_WEEKS = 156, 130


def _parameters(decay, half):
    decay, half = np.asarray(decay, dtype=float), np.asarray(half, dtype=float)
    if decay.shape != (3,) or half.shape != (3,) or not np.isfinite(decay).all() or not np.isfinite(half).all():
        raise ValueError("Three finite decay and half-saturation values are required")
    if (decay < 0).any() or (decay >= 1).any() or (half <= 0).any():
        raise ValueError("Decay must be in [0, 1), and half-saturation must be positive")
    return decay, half


def adstock(spend, decay):
    spend = np.asarray(spend, dtype=float)
    if spend.ndim != 1 or not np.isfinite(spend).all() or (spend < 0).any():
        raise ValueError("Adstock requires finite, nonnegative one-dimensional spend")
    if not np.isfinite(decay) or not 0 <= decay < 1:
        raise ValueError("Decay must be in [0, 1)")
    result = np.empty_like(spend)
    carry = 0.0
    for index, value in enumerate(spend):
        carry = value + decay * carry
        result[index] = carry
    return result


def hill(values, half):
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or not np.isfinite(half) or half <= 0:
        raise ValueError("Hill inputs must be nonnegative and half-saturation positive")
    return values / (half + values)


def controls(length):
    t = np.arange(length, dtype=float)
    return np.column_stack([np.ones(length), t / 52] + [f(2 * np.pi * k * t / 52) for k in (1, 2) for f in (np.sin, np.cos)])


def media_design(spend, decay=DECAY, half=HALF):
    decay, half = _parameters(decay, half)
    spend = np.asarray(spend, dtype=float)
    if spend.ndim != 2 or spend.shape[1] != 3:
        raise ValueError("Spend must have exactly three channel columns")
    response = np.column_stack([hill(adstock(spend[:, i], decay[i]), half[i]) for i in range(3)])
    return np.column_stack([controls(len(spend)), response])


def generate_weekly(seed=SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(WEEKS)
    # Independent random campaign variation, not an observational market dataset.
    spend = rng.uniform([3500, 2500, 2000], [17000, 14000, 12000], size=(WEEKS, 3))
    spend *= (1 + 0.13 * np.sin(2 * np.pi * t[:, None] / 13 + np.arange(3)))
    design = media_design(spend)
    coefficients = np.r_[42000, 5200, 5000, 0, 0, 2500, TRUE_COEFFICIENTS]
    revenue = design @ coefficients + rng.normal(0, 650, WEEKS)
    frame = pd.DataFrame(spend, columns=CHANNELS)
    frame.insert(0, "week", pd.date_range("2022-01-03", periods=WEEKS, freq="W-MON").strftime("%Y-%m-%d"))
    frame["revenue"] = revenue
    return frame


@dataclass(frozen=True)
class MediaFit:
    coefficients: np.ndarray
    decay: np.ndarray
    half: np.ndarray
    train_weeks: int

    def predict(self, spend):
        return media_design(spend, self.decay, self.half) @ self.coefficients


def fit_media(frame: pd.DataFrame, train_weeks=TRAIN_WEEKS, decay=DECAY, half=HALF) -> MediaFit:
    required = {"week", "revenue", *CHANNELS}
    if not required <= set(frame.columns):
        raise ValueError(f"Missing synthetic fields: {sorted(required - set(frame.columns))}")
    if train_weeks < 52 or train_weeks >= len(frame):
        raise ValueError("Need at least 52 training weeks and an untouched holdout")
    dates = pd.to_datetime(frame["week"], format="%Y-%m-%d", errors="raise")
    if dates.isna().any() or not dates.diff().iloc[1:].eq(pd.Timedelta(days=7)).all():
        raise ValueError("Synthetic weeks must be unique, consecutive and chronological")
    decay, half = _parameters(decay, half)
    # Slice before fitting or transforming: no holdout targets enter the solver.
    train = frame.iloc[:train_weeks]
    target = train["revenue"].to_numpy(dtype=float)
    if not np.isfinite(target).all() or (target < 0).any():
        raise ValueError("Training revenue must be finite and nonnegative")
    design = media_design(train[list(CHANNELS)].to_numpy(), decay, half)
    lower = np.r_[np.full(6, -np.inf), np.zeros(3)]
    result = lsq_linear(design, target, bounds=(lower, np.full(9, np.inf)), tol=1e-12, max_iter=1000)
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError(f"Media fit failed: {result.message}")
    return MediaFit(result.x.copy(), decay.copy(), half.copy(), train_weeks)


def steady_state_revenue(spend, fit: MediaFit) -> float:
    """Modelled media response above zero-media steady state, not causal ROI."""
    spend = np.asarray(spend, dtype=float)
    decay, half = _parameters(fit.decay, fit.half)
    if spend.shape != (3,) or not np.isfinite(spend).all() or (spend < 0).any():
        raise ValueError("Expected three nonnegative finite spend amounts")
    coefficients = np.asarray(fit.coefficients, dtype=float)
    if coefficients.shape != (9,) or not np.isfinite(coefficients).all() or (coefficients[-3:] < 0).any():
        raise ValueError("Expected finite fitted coefficients with nonnegative media effects")
    steady_adstock = spend * (1 / (1 - decay))
    return float(np.sum(coefficients[-3:] * (steady_adstock / (half + steady_adstock))))


def optimize_budget(budget: float, fit: MediaFit, minimum=0.1, maximum=0.6) -> dict:
    if not np.isfinite(budget) or budget <= 0:
        raise ValueError("Budget must be finite and positive")
    if not np.isfinite([minimum, maximum]).all() or not 0 <= minimum <= maximum <= 1 or 3 * minimum > 1 or 3 * maximum < 1:
        raise ValueError("Infeasible share bounds")
    equal = np.full(3, 1 / 3)
    balanced = steady_state_revenue(budget * equal, fit)
    effective_half = fit.half * (1 - fit.decay)

    def objective(shares):
        return -steady_state_revenue(budget * shares, fit) / 10000

    def gradient(shares):
        return -fit.coefficients[-3:] * budget * effective_half / (effective_half + budget * shares) ** 2 / 10000

    result = minimize(objective, equal, jac=gradient, method="SLSQP", bounds=[(minimum, maximum)] * 3,
                      constraints=[{"type": "eq", "fun": lambda s: s.sum() - 1, "jac": lambda s: np.ones(3)}],
                      options={"ftol": 1e-12, "maxiter": 300})
    shares = result.x
    if not result.success or abs(shares.sum() - 1) > 1e-8 or (shares < minimum - 1e-8).any() or (shares > maximum + 1e-8).any():
        raise RuntimeError(f"Budget optimization failed: {result.message}")
    response = steady_state_revenue(budget * shares, fit)
    if response < balanced - 1e-6:
        raise RuntimeError("Optimized plan is worse than its feasible equal-split starting point")
    return {"budget": float(budget), "shares": dict(zip(CHANNELS, map(float, shares))), "incremental_revenue": response,
            "balanced_revenue": balanced, "gain_vs_balanced": response - balanced, "optimizer_success": True}


def build_media(seed=SEED) -> dict:
    frame = generate_weekly(seed)
    fit = fit_media(frame)
    predicted = fit.predict(frame[list(CHANNELS)].to_numpy())
    actual = frame["revenue"].to_numpy()
    model_metrics = regression_metrics(actual[TRAIN_WEEKS:], predicted[TRAIN_WEEKS:])
    baseline = actual[TRAIN_WEEKS - 52:WEEKS - 52]
    baseline_metrics = regression_metrics(actual[TRAIN_WEEKS:], baseline)
    frame["predicted"] = predicted
    frame["split"] = np.where(np.arange(WEEKS) < TRAIN_WEEKS, "train", "test")
    frame["baseline_predicted"] = [None] * TRAIN_WEEKS + list(baseline)
    training_min = frame.iloc[:TRAIN_WEEKS][list(CHANNELS)].min().to_numpy()
    training_max = frame.iloc[:TRAIN_WEEKS][list(CHANNELS)].max().to_numpy()
    plans = []
    for budget in range(10000, 100001, 5000):
        plan = optimize_budget(budget, fit)
        spend = budget * np.array([plan["shares"][name] for name in CHANNELS])
        plan["outside_training_spend_range"] = bool(((spend < training_min) | (spend > training_max)).any())
        plans.append(plan)
    return {
        "synthetic": True, "seed": seed, "currency": "GBP",
        "model_name": "nonnegative_adstock_hill", "model_label": "Nonnegative adstock + Hill regression",
        "channels": [{"id": name, "name": name.title(), "decay": float(fit.decay[i]), "half_saturation": float(fit.half[i]),
                      "steady_state_multiplier": float(1 / (1 - fit.decay[i])),
                      "coefficient": float(fit.coefficients[-3 + i]), "generating_coefficient": float(TRUE_COEFFICIENTS[i]),
                      "train_spend_min": float(training_min[i]), "train_spend_max": float(training_max[i])} for i, name in enumerate(CHANNELS)],
        "weekly": frame.astype(object).where(frame.notna(), None).to_dict("records"),
        "metrics": {"model_mae": model_metrics["mae"], "baseline_mae": baseline_metrics["mae"],
                    "model_name": "nonnegative_adstock_hill", "model_label": "Nonnegative adstock + Hill regression",
                    "baseline_name": "seasonal_naive", "baseline_label": "52-week seasonal naive",
                    "model_rmse": model_metrics["rmse"], "baseline_rmse": baseline_metrics["rmse"],
                    "model_wape": model_metrics["wape"], "baseline_wape": baseline_metrics["wape"],
                    "holdout_weeks": WEEKS - TRAIN_WEEKS, "train_weeks": TRAIN_WEEKS,
                    "train_end": frame.iloc[TRAIN_WEEKS - 1]["week"], "test_start": frame.iloc[TRAIN_WEEKS]["week"], "test_end": frame.iloc[-1]["week"],
                    "baseline": "52-week seasonal naive", "validation_weeks": 0},
        "plans": plans,
        "methodology": [
            "Entire marketing dataset is a seeded simulation in GBP; it has no connection to CAB USD observations or real Ekimetrics client data.",
            "156 consecutive weeks; first 130 train, final 26 test. No inner validation or hyperparameter selection was performed.",
            "Adstock a[t] = spend[t] + decay * a[t-1], initialized at zero; Hill exponent 1: a/(half+a).",
            "Decay and half-saturation are fixed to the known simulation settings, not estimated. This is an intentionally favourable, correctly specified synthetic demonstration.",
            "Training-only scipy lsq_linear estimates an intercept, linear trend, two annual Fourier pairs and three nonnegative media coefficients.",
            "Holdout predictions are conditional on observed holdout spend; causal adstock carries only past/current spend, never future spend or holdout revenue. Training predictions are in-sample.",
            "The baseline repeats revenue from 52 weeks earlier; all 26 baseline source weeks precede the fixed holdout origin. WAPE is a fraction, not a percentage.",
            "SLSQP maximizes predicted weekly media response with shares summing to one and each between 10% and 60%, for weekly budgets GBP 10000 to 100000 in increments of 5000.",
            "Plans assume indefinitely repeated constant weekly spend: steady-state adstock = spend/(1-decay). Incremental revenue means modelled media response versus zero-media steady state, excluding baseline trend/seasonality.",
            "Balanced revenue uses the same fitted response and equal one-third shares. Neither response is net profit, causal ROI, an immediate one-week effect, or a real allocation recommendation.",
            "Some plans extrapolate beyond observed training spend; they are flagged. Parameter uncertainty, auctions, interactions, competitive response and business constraints beyond share bounds are omitted.",
        ],
    }
