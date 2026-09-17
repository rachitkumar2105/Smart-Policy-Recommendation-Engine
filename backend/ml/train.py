"""Train and evaluate an insurance-charges regression model.

Dataset: Medical Cost Personal Datasets ("insurance.csv"), 1,338 real rows,
columns age/sex/bmi/children/smoker/region/charges. Publicly distributed,
commonly used for regression teaching (e.g. via the stedy/Machine-Learning-
with-R-datasets GitHub repo).

Trains a Linear Regression baseline and a Gradient Boosting Regressor on an
80/20 train/test split, reports real R²/MAE/RMSE for both on the held-out
test set, and persists whichever one actually scores higher R² on that test
set (no pre-decided winner).

Run with: python -m ml.train
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

DATA_PATH = Path(__file__).parent / "data" / "insurance.csv"
MODEL_PATH = Path(__file__).parent / "model.joblib"
METRICS_PATH = Path(__file__).parent / "metrics.json"

CATEGORICAL = ["sex", "smoker", "region"]
NUMERIC = ["age", "bmi", "children"]
TARGET = "charges"


def build_pipeline(estimator):
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(drop="if_binary"), CATEGORICAL),
        ],
        remainder="passthrough",
    )
    return Pipeline([("preprocess", preprocessor), ("model", estimator)])


def evaluate(pipeline, X_test, y_test) -> dict:
    preds = pipeline.predict(X_test)
    return {
        "r2": round(r2_score(y_test, preds), 4),
        "mae": round(mean_absolute_error(y_test, preds), 2),
        "rmse": round(root_mean_squared_error(y_test, preds), 2),
    }


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    X = df[CATEGORICAL + NUMERIC]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    candidates = {
        "linear_regression": build_pipeline(LinearRegression()),
        "gradient_boosting": build_pipeline(
            GradientBoostingRegressor(random_state=42, n_estimators=200, max_depth=3)
        ),
    }

    results = {}
    for name, pipeline in candidates.items():
        pipeline.fit(X_train, y_train)
        results[name] = evaluate(pipeline, X_test, y_test)
        print(f"{name}: {results[name]}")

    best_name = max(results, key=lambda n: results[n]["r2"])
    best_pipeline = candidates[best_name]
    print(f"\nSelected: {best_name} (highest test R²: {results[best_name]['r2']})")

    joblib.dump(best_pipeline, MODEL_PATH)

    charges_train = y_train.to_numpy()
    normalization = {
        "charges_mean": round(float(np.mean(charges_train)), 2),
        "charges_std": round(float(np.std(charges_train)), 2),
    }

    METRICS_PATH.write_text(
        json.dumps(
            {
                "dataset_rows": len(df),
                "train_rows": len(X_train),
                "test_rows": len(X_test),
                "test_size": 0.2,
                "random_state": 42,
                "candidates": results,
                "selected_model": best_name,
                "normalization": normalization,
            },
            indent=2,
        )
    )
    print(f"\nSaved model to {MODEL_PATH}")
    print(f"Saved metrics to {METRICS_PATH}")


if __name__ == "__main__":
    main()
