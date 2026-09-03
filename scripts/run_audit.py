from __future__ import annotations

import argparse
import json

import pandas as pd

from football_audit.config import INTERIM_DIR, PROCESSED_DIR, REPORTS_DIR, RESULTS_DIR
from football_audit.evaluation import run_temporal_audit
from football_audit.reporting import write_audit_figures, write_audit_report


def run(n_bootstrap: int = 2000, seed: int = 42) -> dict[str, object]:
    matches_path = INTERIM_DIR / "matches.parquet"
    if not matches_path.exists():
        raise FileNotFoundError(
            "missing data/interim/matches.parquet; run scripts/build_dataset.py first"
        )
    matches = pd.read_parquet(matches_path)
    matches["match_date"] = pd.to_datetime(matches["match_date"])
    payload, slices, calibration_bins, predictions = run_temporal_audit(
        matches,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "audit_metrics.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    slices.to_csv(RESULTS_DIR / "slice_metrics.csv", index=False)
    calibration_bins.to_csv(RESULTS_DIR / "calibration_bins.csv", index=False)
    predictions.to_parquet(PROCESSED_DIR / "fold_predictions.parquet", index=False)
    metrics = pd.DataFrame(payload["metric_records"])
    write_audit_figures(metrics, calibration_bins)
    write_audit_report(REPORTS_DIR / "market_probability_audit.md", payload, slices)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-resamples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    payload = run(n_bootstrap=args.bootstrap_resamples, seed=args.seed)
    print(payload["decision"]["recommendation"])


if __name__ == "__main__":
    main()
