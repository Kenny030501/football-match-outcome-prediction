from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, recall_score

from football_audit.config import CLASS_ORDER, FOLDS
from football_audit.features import MARKET_PROBABILITY_COLUMNS
from football_audit.models import (
    build_augmented_model,
    build_recalibrator,
    market_log_features,
    ordered_probabilities,
)

MODEL_NAMES = ("market_raw", "market_recalibrated", "market_plus_public")


def one_hot_target(target: pd.Series) -> np.ndarray:
    mapping = {label: index for index, label in enumerate(CLASS_ORDER)}
    encoded = np.zeros((len(target), len(CLASS_ORDER)), dtype=float)
    for row, label in enumerate(target):
        encoded[row, mapping[label]] = 1.0
    return encoded


def row_log_losses(target: pd.Series, probabilities: np.ndarray) -> np.ndarray:
    mapping = {label: index for index, label in enumerate(CLASS_ORDER)}
    positions = np.array([mapping[label] for label in target])
    return -np.log(np.clip(probabilities[np.arange(len(target)), positions], 1e-15, 1.0))


def row_brier_scores(target: pd.Series, probabilities: np.ndarray) -> np.ndarray:
    return np.square(probabilities - one_hot_target(target)).sum(axis=1)


def probability_metrics(target: pd.Series, probabilities: np.ndarray) -> dict[str, float]:
    prediction = np.array(CLASS_ORDER)[np.argmax(probabilities, axis=1)]
    recalls = recall_score(target, prediction, labels=CLASS_ORDER, average=None, zero_division=0)
    return {
        "log_loss": float(row_log_losses(target, probabilities).mean()),
        "brier": float(row_brier_scores(target, probabilities).mean()),
        "accuracy": float(accuracy_score(target, prediction)),
        "macro_f1": float(
            f1_score(
                target,
                prediction,
                labels=CLASS_ORDER,
                average="macro",
                zero_division=0,
            )
        ),
        "recall_home": float(recalls[0]),
        "recall_draw": float(recalls[1]),
        "recall_away": float(recalls[2]),
    }


def expected_calibration_error(
    target: pd.Series,
    probabilities: np.ndarray,
    class_label: str,
    bins: int = 10,
) -> float:
    class_index = CLASS_ORDER.index(class_label)
    predicted = probabilities[:, class_index]
    observed = (target.to_numpy() == class_label).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    assignments = np.clip(np.digitize(predicted, edges[1:-1], right=False), 0, bins - 1)
    error = 0.0
    for bucket in range(bins):
        mask = assignments == bucket
        if mask.any():
            error += mask.mean() * abs(predicted[mask].mean() - observed[mask].mean())
    return float(error)


def _cluster_bootstrap_ci(
    values: np.ndarray,
    clusters: pd.Series,
    n_bootstrap: int,
    seed: int,
) -> tuple[float, float]:
    frame = pd.DataFrame({"value": values, "cluster": clusters.to_numpy()})
    grouped = frame.groupby("cluster", sort=True)["value"].agg(["sum", "count"])
    sums = grouped["sum"].to_numpy()
    counts = grouped["count"].to_numpy()
    rng = np.random.default_rng(seed)
    samples = rng.integers(0, len(grouped), size=(n_bootstrap, len(grouped)))
    estimates = sums[samples].sum(axis=1) / counts[samples].sum(axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975])
    return float(low), float(high)


def _cluster_keys(frame: pd.DataFrame) -> pd.Series:
    calendar = frame["match_date"].dt.isocalendar()
    return (
        frame["season"].astype(str)
        + "|"
        + calendar["year"].astype(str)
        + "-"
        + calendar["week"].astype(str)
    )


def _metric_values(
    metric: str,
    target: pd.Series,
    probabilities: np.ndarray,
) -> np.ndarray:
    if metric == "log_loss":
        return row_log_losses(target, probabilities)
    if metric == "brier":
        return row_brier_scores(target, probabilities)
    raise ValueError(f"unsupported bootstrap metric: {metric}")


def _confidence_band(probabilities: np.ndarray) -> pd.Categorical:
    maximum = probabilities.max(axis=1)
    return pd.cut(
        maximum,
        bins=[0.0, 0.45, 0.60, 0.75, 1.0],
        labels=["below_45pct", "45_to_60pct", "60_to_75pct", "above_75pct"],
        include_lowest=True,
    )


def build_slice_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    raw = predictions[[f"market_raw_p_{label.lower()}" for label in CLASS_ORDER]].to_numpy()
    working = predictions.copy()
    working["confidence_band"] = _confidence_band(raw)
    working["overround_quintile"] = pd.qcut(
        working["market_overround"].rank(method="first"),
        5,
        labels=["Q1_low", "Q2", "Q3", "Q4", "Q5_high"],
    )
    slices: list[tuple[str, pd.Series]] = [
        ("league", working["league"]),
        ("season", working["season"]),
        ("outcome", working["ftr"]),
        ("confidence", working["confidence_band"].astype(str)),
        ("overround", working["overround_quintile"].astype(str)),
    ]
    records: list[dict[str, object]] = []
    for slice_type, values in slices:
        for slice_value in sorted(values.dropna().unique()):
            mask = values == slice_value
            target = working.loc[mask, "ftr"]
            for model in MODEL_NAMES:
                probability_columns = [f"{model}_p_{label.lower()}" for label in CLASS_ORDER]
                probabilities = working.loc[mask, probability_columns].to_numpy()
                metrics = probability_metrics(target, probabilities)
                records.append(
                    {
                        "slice_type": slice_type,
                        "slice_value": str(slice_value),
                        "n": int(mask.sum()),
                        "model": model,
                        "log_loss": metrics["log_loss"],
                        "brier": metrics["brier"],
                        "accuracy": metrics["accuracy"],
                    }
                )
    return pd.DataFrame(records)


def build_calibration_bins(predictions: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for model in MODEL_NAMES:
        for label in CLASS_ORDER:
            predicted = predictions[f"{model}_p_{label.lower()}"]
            order = predicted.rank(method="first")
            bucket = pd.qcut(order, bins, labels=False)
            observed = (predictions["ftr"] == label).astype(float)
            grouped = pd.DataFrame(
                {"predicted": predicted, "observed": observed, "bucket": bucket}
            ).groupby("bucket", sort=True)
            for bucket_id, group in grouped:
                records.append(
                    {
                        "model": model,
                        "class": label,
                        "bin": int(bucket_id) + 1,
                        "n": len(group),
                        "average_probability": float(group["predicted"].mean()),
                        "observed_rate": float(group["observed"].mean()),
                    }
                )
    return pd.DataFrame(records)


def _comparison(
    predictions: pd.DataFrame,
    candidate: str,
    baseline: str,
    metric: str,
    fold_metric_lookup: dict[tuple[str, str, str], float],
    n_bootstrap: int,
    seed: int,
) -> dict[str, object]:
    target = predictions["ftr"]
    candidate_probability = predictions[
        [f"{candidate}_p_{label.lower()}" for label in CLASS_ORDER]
    ].to_numpy()
    baseline_probability = predictions[
        [f"{baseline}_p_{label.lower()}" for label in CLASS_ORDER]
    ].to_numpy()
    difference = _metric_values(metric, target, candidate_probability) - _metric_values(
        metric, target, baseline_probability
    )
    low, high = _cluster_bootstrap_ci(
        difference,
        _cluster_keys(predictions),
        n_bootstrap,
        seed,
    )
    folds_improved = sum(
        fold_metric_lookup[(fold.name, candidate, metric)]
        < fold_metric_lookup[(fold.name, baseline, metric)]
        for fold in FOLDS
    )
    return {
        "candidate": candidate,
        "baseline": baseline,
        "metric": metric,
        "delta": float(difference.mean()),
        "ci_low": low,
        "ci_high": high,
        "folds_improved": int(folds_improved),
        "folds_total": len(FOLDS),
    }


def run_temporal_audit(
    matches: pd.DataFrame,
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metric_records: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    fold_metric_lookup: dict[tuple[str, str, str], float] = {}

    for fold_index, fold in enumerate(FOLDS):
        train = matches[matches["season"].isin(fold.train_seasons)].copy()
        test = matches[matches["season"] == fold.test_season].copy()
        if train.empty or test.empty:
            raise ValueError(f"empty train or test sample for {fold.name}")
        if train["match_date"].max() >= test["match_date"].min():
            raise ValueError(f"temporal overlap in {fold.name}")

        recalibrator = build_recalibrator().fit(market_log_features(train), train["ftr"])
        augmented = build_augmented_model().fit(train, train["ftr"])
        probabilities = {
            "market_raw": test[MARKET_PROBABILITY_COLUMNS].to_numpy(),
            "market_recalibrated": ordered_probabilities(recalibrator, market_log_features(test)),
            "market_plus_public": ordered_probabilities(augmented, test),
        }

        prediction_frame = test[
            [
                "season",
                "league",
                "match_date",
                "home_team",
                "away_team",
                "ftr",
                "market_overround",
            ]
        ].copy()
        prediction_frame["fold"] = fold.name
        for model, model_probabilities in probabilities.items():
            for class_index, label in enumerate(CLASS_ORDER):
                prediction_frame[f"{model}_p_{label.lower()}"] = model_probabilities[:, class_index]
            metrics = probability_metrics(test["ftr"], model_probabilities)
            for metric, value in metrics.items():
                low: float | None = None
                high: float | None = None
                if metric in {"log_loss", "brier"}:
                    values = _metric_values(metric, test["ftr"], model_probabilities)
                    low, high = _cluster_bootstrap_ci(
                        values,
                        _cluster_keys(test),
                        n_bootstrap,
                        seed
                        + fold_index * 100
                        + MODEL_NAMES.index(model) * 10
                        + (metric == "brier"),
                    )
                metric_records.append(
                    {
                        "fold": fold.name,
                        "test_season": fold.test_season,
                        "model": model,
                        "metric": metric,
                        "value": value,
                        "ci_low": low,
                        "ci_high": high,
                    }
                )
                fold_metric_lookup[(fold.name, model, metric)] = value
            for label in CLASS_ORDER:
                metric_records.append(
                    {
                        "fold": fold.name,
                        "test_season": fold.test_season,
                        "model": model,
                        "metric": f"ece_{label.lower()}",
                        "value": expected_calibration_error(
                            test["ftr"], model_probabilities, label
                        ),
                        "ci_low": None,
                        "ci_high": None,
                    }
                )
        prediction_frames.append(prediction_frame)

    predictions = pd.concat(prediction_frames, ignore_index=True)
    comparisons = []
    pairs = [
        ("market_recalibrated", "market_raw"),
        ("market_plus_public", "market_recalibrated"),
    ]
    for pair_index, (candidate, baseline) in enumerate(pairs):
        for metric_index, metric in enumerate(("log_loss", "brier")):
            comparisons.append(
                _comparison(
                    predictions,
                    candidate,
                    baseline,
                    metric,
                    fold_metric_lookup,
                    n_bootstrap,
                    seed + 1000 + pair_index * 100 + metric_index,
                )
            )

    comparison_lookup = {
        (row["candidate"], row["baseline"], row["metric"]): row for row in comparisons
    }
    calibration_log = comparison_lookup[("market_recalibrated", "market_raw", "log_loss")]
    calibration_brier = comparison_lookup[("market_recalibrated", "market_raw", "brier")]
    augmentation_log = comparison_lookup[("market_plus_public", "market_recalibrated", "log_loss")]
    augmentation_brier = comparison_lookup[("market_plus_public", "market_recalibrated", "brier")]
    calibration_qualifies = (
        calibration_log["folds_improved"] >= 3
        and calibration_brier["folds_improved"] >= 3
        and calibration_log["ci_high"] < 0
    )
    augmentation_qualifies = (
        calibration_qualifies
        and augmentation_log["folds_improved"] >= 3
        and augmentation_brier["folds_improved"] >= 3
        and augmentation_log["ci_high"] < 0
    )
    recommendation = (
        "augment_market_probabilities"
        if augmentation_qualifies
        else "recalibrate_market_probabilities"
        if calibration_qualifies
        else "use_market_probabilities_as_is"
    )
    pooled_metrics = {}
    for model in MODEL_NAMES:
        model_probabilities = predictions[
            [f"{model}_p_{label.lower()}" for label in CLASS_ORDER]
        ].to_numpy()
        pooled_metrics[model] = probability_metrics(predictions["ftr"], model_probabilities)
        pooled_metrics[model].update(
            {
                f"ece_{label.lower()}": expected_calibration_error(
                    predictions["ftr"], model_probabilities, label
                )
                for label in CLASS_ORDER
            }
        )
    payload = {
        "class_order": list(CLASS_ORDER),
        "audit_rows": len(matches),
        "evaluated_rows": len(predictions),
        "bootstrap_resamples": n_bootstrap,
        "random_seed": seed,
        "folds": [
            {
                "name": fold.name,
                "train_seasons": list(fold.train_seasons),
                "test_season": fold.test_season,
            }
            for fold in FOLDS
        ],
        "metric_records": metric_records,
        "pooled_metrics": pooled_metrics,
        "comparisons": comparisons,
        "decision": {
            "recommendation": recommendation,
            "calibration_qualifies": calibration_qualifies,
            "augmentation_qualifies": augmentation_qualifies,
        },
    }
    slices = build_slice_metrics(predictions)
    calibration_bins = build_calibration_bins(predictions)
    return payload, slices, calibration_bins, predictions
