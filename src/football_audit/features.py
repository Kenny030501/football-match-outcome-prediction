from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MARKET_PROBABILITY_COLUMNS = ["market_p_home", "market_p_draw", "market_p_away"]
PUBLIC_NUMERIC_FEATURES = [
    *MARKET_PROBABILITY_COLUMNS,
    "market_overround",
    "market_entropy",
    "elo_diff_home_adjusted",
    "points5_diff",
    "goal_diff5_diff",
    "rest_days_diff",
    "home_history_n",
    "away_history_n",
    "season_progress",
]
CATEGORICAL_FEATURES = ["league"]
FORBIDDEN_SAME_MATCH_FEATURES = {
    "ftr",
    "fthg",
    "ftag",
    "hthg",
    "htag",
    "htr",
    "hs",
    "as",
    "hst",
    "ast",
    "hc",
    "ac",
    "hy",
    "ay",
    "hr",
    "ar",
    "highscoring",
}


@dataclass
class TeamState:
    rating: float = 1500.0
    points: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    goal_difference: deque[float] = field(default_factory=lambda: deque(maxlen=5))
    last_date: pd.Timestamp | None = None


def _mean_or_nan(values: deque[float]) -> float:
    return float(np.mean(values)) if values else np.nan


def _actual_home_score(result: str) -> float:
    return 1.0 if result == "H" else 0.0 if result == "A" else 0.5


def build_point_in_time_features(matches: pd.DataFrame) -> pd.DataFrame:
    ordered = matches.sort_values(["match_date", "league", "home_team", "away_team"]).reset_index(
        drop=True
    )
    states: dict[str, TeamState] = defaultdict(TeamState)
    feature_rows: list[dict[str, float]] = []

    for match_date, day in ordered.groupby("match_date", sort=True):
        day_features: list[dict[str, float]] = []
        rating_updates: dict[str, float] = defaultdict(float)
        form_updates: list[tuple[str, float, float, pd.Timestamp]] = []
        for row in day.itertuples(index=False):
            home = states[row.home_team]
            away = states[row.away_team]
            home_rest = (match_date - home.last_date).days if home.last_date is not None else np.nan
            away_rest = (match_date - away.last_date).days if away.last_date is not None else np.nan
            day_features.append(
                {
                    "elo_home": home.rating,
                    "elo_away": away.rating,
                    "elo_diff_home_adjusted": home.rating + 60.0 - away.rating,
                    "home_points5": _mean_or_nan(home.points),
                    "away_points5": _mean_or_nan(away.points),
                    "points5_diff": _mean_or_nan(home.points) - _mean_or_nan(away.points),
                    "home_goal_diff5": _mean_or_nan(home.goal_difference),
                    "away_goal_diff5": _mean_or_nan(away.goal_difference),
                    "goal_diff5_diff": _mean_or_nan(home.goal_difference)
                    - _mean_or_nan(away.goal_difference),
                    "home_rest_days": home_rest,
                    "away_rest_days": away_rest,
                    "rest_days_diff": home_rest - away_rest,
                    "home_history_n": len(home.points),
                    "away_history_n": len(away.points),
                }
            )
            expected_home = 1.0 / (1.0 + 10.0 ** ((away.rating - home.rating - 60.0) / 400.0))
            rating_delta = 20.0 * (_actual_home_score(row.ftr) - expected_home)
            rating_updates[row.home_team] += rating_delta
            rating_updates[row.away_team] -= rating_delta
            home_points = 3.0 if row.ftr == "H" else 1.0 if row.ftr == "D" else 0.0
            away_points = 3.0 if row.ftr == "A" else 1.0 if row.ftr == "D" else 0.0
            goal_difference = float(row.fthg - row.ftag)
            form_updates.extend(
                [
                    (row.home_team, home_points, goal_difference, match_date),
                    (row.away_team, away_points, -goal_difference, match_date),
                ]
            )
        feature_rows.extend(day_features)
        for team, delta in rating_updates.items():
            states[team].rating += delta
        for team, points, goal_difference, date in form_updates:
            states[team].points.append(points)
            states[team].goal_difference.append(goal_difference)
            states[team].last_date = date

    featured = pd.concat([ordered, pd.DataFrame(feature_rows)], axis=1)
    odds = featured[["avg_close_home", "avg_close_draw", "avg_close_away"]]
    inverse = 1.0 / odds
    inverse_sum = inverse.sum(axis=1)
    probabilities = inverse.div(inverse_sum, axis=0)
    probabilities.columns = MARKET_PROBABILITY_COLUMNS
    featured = pd.concat([featured, probabilities], axis=1)
    featured["market_overround"] = inverse_sum - 1.0
    featured["market_entropy"] = -(probabilities * np.log(probabilities)).sum(axis=1)
    season_start = featured.groupby(["season", "league"])["match_date"].transform("min")
    featured["season_progress"] = ((featured["match_date"] - season_start).dt.days / 365.0).clip(
        0, 1
    )
    audit = featured.loc[featured["is_audit"]].copy()
    if not np.allclose(audit[MARKET_PROBABILITY_COLUMNS].sum(axis=1), 1.0, atol=1e-12):
        raise ValueError("normalized market probabilities do not sum to one")
    return audit.reset_index(drop=True)
