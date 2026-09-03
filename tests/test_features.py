from __future__ import annotations

import pandas as pd

from football_audit.features import (
    FORBIDDEN_SAME_MATCH_FEATURES,
    MARKET_PROBABILITY_COLUMNS,
    PUBLIC_NUMERIC_FEATURES,
    build_point_in_time_features,
)


def _matches() -> pd.DataFrame:
    rows = [
        ("1819", "2018-08-01", "Alpha", "Beta", "H", 2, 0, False),
        ("1920", "2019-08-01", "Alpha", "Gamma", "H", 1, 0, True),
        ("1920", "2019-08-01", "Alpha", "Delta", "A", 0, 1, True),
        ("1920", "2019-08-08", "Alpha", "Beta", "D", 1, 1, True),
    ]
    return pd.DataFrame(
        [
            {
                "season": season,
                "league": "E0",
                "match_date": pd.Timestamp(date),
                "kickoff_time": "15:00",
                "home_team": home,
                "away_team": away,
                "ftr": result,
                "fthg": home_goals,
                "ftag": away_goals,
                "avg_close_home": 2.0 if audit else float("nan"),
                "avg_close_draw": 3.5 if audit else float("nan"),
                "avg_close_away": 4.0 if audit else float("nan"),
                "b365_close_home": 2.0 if audit else float("nan"),
                "b365_close_draw": 3.5 if audit else float("nan"),
                "b365_close_away": 4.0 if audit else float("nan"),
                "is_audit": audit,
            }
            for season, date, home, away, result, home_goals, away_goals, audit in rows
        ]
    )


def test_probability_normalization_and_feature_allowlist() -> None:
    featured = build_point_in_time_features(_matches())
    assert featured[MARKET_PROBABILITY_COLUMNS].sum(axis=1).round(12).eq(1.0).all()
    assert not (
        {feature.lower() for feature in PUBLIC_NUMERIC_FEATURES} & FORBIDDEN_SAME_MATCH_FEATURES
    )


def test_same_day_matches_share_the_same_pre_day_team_state() -> None:
    featured = build_point_in_time_features(_matches())
    same_day = featured[featured["match_date"] == pd.Timestamp("2019-08-01")]
    assert same_day["elo_home"].nunique() == 1
    assert same_day["home_history_n"].nunique() == 1


def test_future_result_cannot_change_earlier_features() -> None:
    original = _matches()
    changed = original.copy()
    changed.loc[changed["match_date"] == pd.Timestamp("2019-08-08"), ["ftr", "fthg", "ftag"]] = [
        "A",
        0,
        2,
    ]
    original_features = build_point_in_time_features(original)
    changed_features = build_point_in_time_features(changed)
    feature_columns = [
        "elo_home",
        "elo_away",
        "points5_diff",
        "goal_diff5_diff",
        "rest_days_diff",
    ]
    pd.testing.assert_frame_equal(
        original_features[feature_columns],
        changed_features[feature_columns],
    )
