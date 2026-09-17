"""Inference wrapper around the trained insurance-charges regression model.

Loads the persisted pipeline + normalization stats once, then exposes a pure
function that turns a risk profile into a bounded, explainable premium-loading
adjustment — a second, ML-derived signal alongside the existing deterministic
rule-based coefficient (see app/services/scoring.py).
"""

import json
from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).parent / "model.joblib"
METRICS_PATH = Path(__file__).parent / "metrics.json"

# Bounds on the ML-derived adjustment so a single model prediction can never
# dominate or invert the premium — keeps the blended result explainable and
# safe even on out-of-distribution inputs.
MIN_ADJUSTMENT = -0.20
MAX_ADJUSTMENT = 0.50
Z_SCALE = 0.12

_model = None
_normalization = None


def _load() -> None:
    global _model, _normalization
    if _model is None:
        _model = joblib.load(MODEL_PATH)
        _normalization = json.loads(METRICS_PATH.read_text())["normalization"]


def predict_charges(
    age: int, sex: str, bmi: float, children: int, is_smoker: bool, region: str
) -> float:
    """Real model inference: predicted annual medical charges for this profile."""
    _load()
    row = pd.DataFrame(
        [
            {
                "sex": sex,
                "smoker": "yes" if is_smoker else "no",
                "region": region,
                "age": age,
                "bmi": bmi,
                "children": children,
            }
        ]
    )
    prediction = _model.predict(row)[0]
    return round(float(prediction), 2)


def ml_adjustment(
    age: int, sex: str, bmi: float, children: int, is_smoker: bool, region: str
) -> tuple[float, float]:
    """Returns (predicted_charges, bounded_premium_adjustment).

    The adjustment is a z-score of the predicted charges against the training
    population, scaled down and clipped so it acts as a bounded loading on top
    of the base premium rather than an unbounded dollar figure.
    """
    _load()
    predicted = predict_charges(age, sex, bmi, children, is_smoker, region)
    mean = _normalization["charges_mean"]
    std = _normalization["charges_std"]
    z = (predicted - mean) / std if std else 0.0
    adjustment = max(MIN_ADJUSTMENT, min(MAX_ADJUSTMENT, z * Z_SCALE))
    return predicted, round(adjustment, 4)
