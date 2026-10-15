"""Shared regression diagnostics, reported in the target's units."""

import numpy as np


def regression_metrics(actual, predicted) -> dict:
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if actual.ndim != 1 or not actual.size or actual.shape != predicted.shape:
        raise ValueError("Metrics require nonempty, equally sized vectors")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Metrics require finite values")
    errors = actual - predicted
    denominator = float(np.abs(actual).sum())
    return {
        "mae": float(np.abs(errors).mean()),
        "rmse": float(np.sqrt(np.mean(errors**2))),
        "wape": float(np.abs(errors).sum() / denominator) if denominator else None,
    }
