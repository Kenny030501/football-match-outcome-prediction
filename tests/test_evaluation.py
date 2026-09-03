from __future__ import annotations

import pandas as pd

from football_audit.config import FOLDS
from football_audit.evaluation import run_temporal_audit


def test_temporal_audit_is_deterministic_and_uses_only_test_seasons(
    synthetic_audit_frame: pd.DataFrame,
) -> None:
    first, first_slices, _, first_predictions = run_temporal_audit(
        synthetic_audit_frame,
        n_bootstrap=20,
        seed=42,
    )
    second, second_slices, _, second_predictions = run_temporal_audit(
        synthetic_audit_frame,
        n_bootstrap=20,
        seed=42,
    )
    assert first == second
    pd.testing.assert_frame_equal(first_slices, second_slices)
    pd.testing.assert_frame_equal(first_predictions, second_predictions)
    assert set(first_predictions["season"]) == {fold.test_season for fold in FOLDS}
    for fold in FOLDS:
        assert set(fold.train_seasons).isdisjoint({fold.test_season})


def test_audit_outputs_all_three_models(synthetic_audit_frame: pd.DataFrame) -> None:
    payload, slices, calibration, predictions = run_temporal_audit(
        synthetic_audit_frame,
        n_bootstrap=10,
        seed=7,
    )
    models = {row["model"] for row in payload["metric_records"]}
    assert models == {"market_raw", "market_recalibrated", "market_plus_public"}
    assert set(slices["slice_type"]) == {
        "league",
        "season",
        "outcome",
        "confidence",
        "overround",
    }
    assert set(calibration["class"]) == {"H", "D", "A"}
    assert len(predictions) > 0
