from __future__ import annotations

import argparse

import pandas as pd

from football_audit.config import (
    EXPECTED_AUDIT_ROWS,
    EXPECTED_SOURCE_FILES,
    INTERIM_DIR,
    REPORTS_DIR,
    RESULTS_DIR,
)
from football_audit.data import acquire_sources, load_sources
from football_audit.features import build_point_in_time_features
from football_audit.reporting import write_data_quality_report


def build(refresh: bool = False) -> pd.DataFrame:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    manifest_records, payloads = acquire_sources(refresh=refresh)
    all_matches, manifest, quarantine = load_sources(manifest_records, payloads)
    if quarantine.empty:
        quarantine = pd.DataFrame(columns=["season", "league", "source_line", "reason"])
    audit_matches = build_point_in_time_features(all_matches)
    manifest.to_csv(RESULTS_DIR / "download_manifest.csv", index=False)
    quarantine.to_csv(RESULTS_DIR / "quarantine.csv", index=False)
    audit_matches.to_parquet(INTERIM_DIR / "matches.parquet", index=False)
    write_data_quality_report(
        REPORTS_DIR / "data_quality.md",
        manifest,
        quarantine,
        all_matches,
        audit_matches,
    )
    failed = manifest[~manifest["status"].isin(["cached", "downloaded"])]
    if len(manifest) != EXPECTED_SOURCE_FILES:
        raise RuntimeError(f"expected {EXPECTED_SOURCE_FILES} source files, found {len(manifest)}")
    if not failed.empty:
        raise RuntimeError(
            f"{len(failed)} source files failed; inspect results/download_manifest.csv"
        )
    if len(audit_matches) != EXPECTED_AUDIT_ROWS:
        raise RuntimeError(
            f"expected {EXPECTED_AUDIT_ROWS} audit rows, found {len(audit_matches)}; source review required"
        )
    return audit_matches


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    matches = build(refresh=args.refresh)
    print(f"Built {len(matches):,} audit rows at data/interim/matches.parquet")


if __name__ == "__main__":
    main()
