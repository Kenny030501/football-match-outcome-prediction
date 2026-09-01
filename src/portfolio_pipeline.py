from __future__ import annotations

import argparse
import io
import json
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"
RESULTS_DIR = ROOT / "results"
LEAGUES = ["E0", "E1", "E2", "E3", "EC"]
STADIUM_URL = "https://opisthokonta.net/wp-content/uploads/2015/03/stadiums_20150302.csv"


def season_codes(start_year: int, end_year: int) -> list[str]:
    return [f"{year % 100:02d}{(year + 1) % 100:02d}" for year in range(start_year, end_year + 1)]


def fetch_csv(url: str, path: Path) -> pd.DataFrame | None:
    if path.exists():
        return pd.read_csv(path, encoding="latin-1")
    response = requests.get(url, timeout=30)
    if response.status_code != 200 or b"," not in response.content[:500]:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return pd.read_csv(io.BytesIO(response.content), encoding="latin-1")


def load_matches(start_year: int, end_year: int) -> pd.DataFrame:
    frames = []
    for season in season_codes(start_year, end_year):
        for league in LEAGUES:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
            path = DATA_DIR / season / f"{league}.csv"
            try:
                frame = fetch_csv(url, path)
            except Exception:
                frame = None
            if frame is None or frame.empty:
                continue
            required = {"Date", "HomeTeam", "AwayTeam", "FTR", "FTHG", "FTAG", "B365H", "B365D", "B365A"}
            if not required.issubset(frame.columns):
                continue
            frame = frame.copy()
            frame["Season"] = season
            frame["League"] = league
            frames.append(frame)
    if not frames:
        raise RuntimeError("No match files could be downloaded")
    matches = pd.concat(frames, ignore_index=True)
    matches["Date"] = pd.to_datetime(matches["Date"], dayfirst=True, errors="coerce", format="mixed")
    matches = matches.dropna(subset=["Date", "FTR", "FTHG", "FTAG", "B365H", "B365D", "B365A"])
    matches = matches[matches["FTR"].isin(["H", "D", "A"])]
    matches = matches[(matches[["B365H", "B365D", "B365A"]] > 0).all(axis=1)]
    return matches.sort_values(["Date", "League", "HomeTeam", "AwayTeam"]).reset_index(drop=True)


def add_static_distance(matches: pd.DataFrame) -> pd.DataFrame:
    matches = matches.copy()
    try:
        response = requests.get(STADIUM_URL, timeout=30)
        response.raise_for_status()
        stadiums = pd.read_csv(io.BytesIO(response.content))
        locations = stadiums[["FDCOUK", "Latitude", "Longitude"]].rename(columns={"FDCOUK": "Team"})
        locations = locations.drop_duplicates("Team")
        home = locations.add_prefix("Home_")
        away = locations.add_prefix("Away_")
        matches = matches.merge(home, left_on="HomeTeam", right_on="Home_Team", how="left")
        matches = matches.merge(away, left_on="AwayTeam", right_on="Away_Team", how="left")
        lat1 = np.radians(matches["Home_Latitude"])
        lat2 = np.radians(matches["Away_Latitude"])
        dlat = lat2 - lat1
        dlon = np.radians(matches["Away_Longitude"] - matches["Home_Longitude"])
        a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
        distance = 6371.0 * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        matches = matches.assign(TravelDistance_km=distance)
    except Exception:
        matches = matches.assign(TravelDistance_km=np.nan)
    return matches


def add_prior_form(matches: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    points: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=window))
    goal_diff: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=window))
    rows = []
    for row in matches.itertuples(index=False):
        home_points = points[row.HomeTeam]
        away_points = points[row.AwayTeam]
        home_goal_diff = goal_diff[row.HomeTeam]
        away_goal_diff = goal_diff[row.AwayTeam]
        rows.append(
            {
                "HomePoints5": np.mean(home_points) if home_points else np.nan,
                "AwayPoints5": np.mean(away_points) if away_points else np.nan,
                "HomeGoalDiff5": np.mean(home_goal_diff) if home_goal_diff else np.nan,
                "AwayGoalDiff5": np.mean(away_goal_diff) if away_goal_diff else np.nan,
                "HomeHistoryN": len(home_points),
                "AwayHistoryN": len(away_points),
            }
        )
        if row.FTR == "H":
            hp, ap = 3.0, 0.0
        elif row.FTR == "A":
            hp, ap = 0.0, 3.0
        else:
            hp, ap = 1.0, 1.0
        diff = float(row.FTHG - row.FTAG)
        points[row.HomeTeam].append(hp)
        points[row.AwayTeam].append(ap)
        goal_diff[row.HomeTeam].append(diff)
        goal_diff[row.AwayTeam].append(-diff)
    return pd.concat([matches.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def build_features(matches: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    matches = add_prior_form(add_static_distance(matches))
    inv = 1.0 / matches[["B365H", "B365D", "B365A"]]
    normalized = inv.div(inv.sum(axis=1), axis=0)
    probabilities = pd.DataFrame(normalized.to_numpy(), columns=["ProbH", "ProbD", "ProbA"], index=matches.index)
    matches = pd.concat([matches.copy(), probabilities], axis=1)
    features = matches[
        [
            "B365H",
            "B365D",
            "B365A",
            "ProbH",
            "ProbD",
            "ProbA",
            "TravelDistance_km",
            "HomePoints5",
            "AwayPoints5",
            "HomeGoalDiff5",
            "AwayGoalDiff5",
            "HomeHistoryN",
            "AwayHistoryN",
            "League",
        ]
    ].copy()
    return features, matches["FTR"].copy()


def preprocessing(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    numeric_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer([("num", numeric_pipeline, numeric), ("cat", categorical_pipeline, categorical)])


def evaluate(name: str, model: Pipeline, x_train: pd.DataFrame, y_train: pd.Series, x_test: pd.DataFrame, y_test: pd.Series) -> dict:
    model.fit(x_train, y_train)
    prediction = model.predict(x_test)
    probability = model.predict_proba(x_test)
    return {
        "model": name,
        "accuracy": float(accuracy_score(y_test, prediction)),
        "macro_f1": float(f1_score(y_test, prediction, average="macro")),
        "log_loss": float(log_loss(y_test, probability, labels=model.classes_)),
    }


def run(start_year: int, end_year: int) -> dict:
    matches = load_matches(start_year, end_year)
    features, target = build_features(matches)
    split = int(len(features) * 0.8)
    x_train, x_test = features.iloc[:split], features.iloc[split:]
    y_train, y_test = target.iloc[:split], target.iloc[split:]

    results = [
        {
            "model": "Always home win",
            "accuracy": float(accuracy_score(y_test, np.repeat("H", len(y_test)))),
            "macro_f1": float(f1_score(y_test, np.repeat("H", len(y_test)), average="macro")),
            "log_loss": None,
        }
    ]
    bookmaker_probability = x_test[["ProbA", "ProbD", "ProbH"]].to_numpy()
    odds_prediction = np.array(["A", "D", "H"])[np.argmax(bookmaker_probability, axis=1)]
    results.append(
        {
            "model": "Bookmaker favorite",
            "accuracy": float(accuracy_score(y_test, odds_prediction)),
            "macro_f1": float(f1_score(y_test, odds_prediction, average="macro")),
            "log_loss": float(log_loss(y_test, bookmaker_probability, labels=["A", "D", "H"])),
        }
    )

    odds_features = ["B365H", "B365D", "B365A", "ProbH", "ProbD", "ProbA"]
    full_numeric = [column for column in features.columns if column != "League"]
    models = [
        (
            "Logistic regression - odds only",
            Pipeline(
                [
                    ("preprocess", preprocessing(odds_features, [])),
                    ("model", LogisticRegression(max_iter=1500, class_weight="balanced")),
                ]
            ),
            odds_features,
        ),
        (
            "Logistic regression - pre-match features",
            Pipeline(
                [
                    ("preprocess", preprocessing(full_numeric, ["League"])),
                    ("model", LogisticRegression(max_iter=1500, class_weight="balanced")),
                ]
            ),
            list(features.columns),
        ),
        (
            "Random forest - pre-match features",
            Pipeline(
                [
                    ("preprocess", preprocessing(full_numeric, ["League"])),
                    (
                        "model",
                        RandomForestClassifier(
                            n_estimators=250,
                            max_depth=16,
                            min_samples_leaf=20,
                            class_weight="balanced",
                            random_state=42,
                            n_jobs=-1,
                        ),
                    ),
                ]
            ),
            list(features.columns),
        ),
        (
            "MLP - pre-match features",
            Pipeline(
                [
                    ("preprocess", preprocessing(full_numeric, ["League"])),
                    (
                        "model",
                        MLPClassifier(
                            hidden_layer_sizes=(64, 32),
                            alpha=0.001,
                            max_iter=300,
                            early_stopping=True,
                            random_state=42,
                        ),
                    ),
                ]
            ),
            list(features.columns),
        ),
    ]
    for name, model, columns in models:
        results.append(evaluate(name, model, x_train[columns], y_train, x_test[columns], y_test))

    payload = {
        "sample_size": int(len(matches)),
        "train_size": int(split),
        "test_size": int(len(matches) - split),
        "train_start": str(matches.iloc[0]["Date"].date()),
        "train_end": str(matches.iloc[split - 1]["Date"].date()),
        "test_start": str(matches.iloc[split]["Date"].date()),
        "test_end": str(matches.iloc[-1]["Date"].date()),
        "feature_policy": "Only pre-match-available odds, static geography, league, and lagged five-match form",
        "results": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "portfolio_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=1998)
    parser.add_argument("--end-year", type=int, default=2023)
    args = parser.parse_args()
    print(json.dumps(run(args.start_year, args.end_year), indent=2))


if __name__ == "__main__":
    main()
