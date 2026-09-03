from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from football_audit.config import CLASS_ORDER
from football_audit.features import (
    CATEGORICAL_FEATURES,
    MARKET_PROBABILITY_COLUMNS,
    PUBLIC_NUMERIC_FEATURES,
)


def market_log_features(frame: pd.DataFrame) -> pd.DataFrame:
    probabilities = frame[MARKET_PROBABILITY_COLUMNS].clip(1e-8, 1.0)
    return np.log(probabilities).rename(columns=lambda column: f"log_{column}")


def build_recalibrator() -> Pipeline:
    return Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs")),
        ]
    )


def build_augmented_model() -> Pipeline:
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocess = ColumnTransformer(
        [
            ("numeric", numeric, PUBLIC_NUMERIC_FEATURES),
            ("categorical", categorical, CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline(
        [
            ("preprocess", preprocess),
            ("model", LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs")),
        ]
    )


def ordered_probabilities(model: Pipeline, features: pd.DataFrame) -> np.ndarray:
    probabilities = model.predict_proba(features)
    class_positions = {label: index for index, label in enumerate(model.classes_)}
    return probabilities[:, [class_positions[label] for label in CLASS_ORDER]]
