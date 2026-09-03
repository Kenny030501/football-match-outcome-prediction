from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR = ROOT / "data" / "interim"
PROCESSED_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = RESULTS_DIR / "figures"

WARMUP_SEASONS = ("1718", "1819")
AUDIT_SEASONS = ("1920", "2021", "2122", "2223", "2324", "2425", "2526")
ALL_SEASONS = WARMUP_SEASONS + AUDIT_SEASONS
LEAGUES = ("E0", "E1", "E2", "E3", "EC")
CLASS_ORDER = ("H", "D", "A")
SOURCE_URL = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
EXPECTED_SOURCE_FILES = 45
EXPECTED_AUDIT_ROWS = 17630

IDENTITY_COLUMNS = ("Date", "HomeTeam", "AwayTeam", "FTR", "FTHG", "FTAG")
AUDIT_ODDS_COLUMNS = ("AvgCH", "AvgCD", "AvgCA")
REFERENCE_ODDS_COLUMNS = ("B365CH", "B365CD", "B365CA")


@dataclass(frozen=True)
class FoldSpec:
    name: str
    train_seasons: tuple[str, ...]
    test_season: str


FOLDS = (
    FoldSpec("test_2223", ("1920", "2021", "2122"), "2223"),
    FoldSpec("test_2324", ("1920", "2021", "2122", "2223"), "2324"),
    FoldSpec("test_2425", ("1920", "2021", "2122", "2223", "2324"), "2425"),
    FoldSpec(
        "test_2526",
        ("1920", "2021", "2122", "2223", "2324", "2425"),
        "2526",
    ),
)
