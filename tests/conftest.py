from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from football_audit.config import AUDIT_SEASONS
from football_audit.features import PUBLIC_NUMERIC_FEATURES


@pytest.fixture
def synthetic_audit_frame() -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(42)
    for season_index, season in enumerate(AUDIT_SEASONS):
        start = pd.Timestamp(2019 + season_index, 8, 1)
        for match_index in range(36):
            result = ("H", "D", "A")[match_index % 3]
            raw = np.array([0.48, 0.27, 0.25]) + rng.normal(0, 0.015, 3)
            raw = np.clip(raw, 0.08, None)
            raw = raw / raw.sum()
            row = {
                "season": season,
                "league": ("E0", "E1", "E2")[match_index % 3],
                "match_date": start + pd.Timedelta(days=match_index * 7),
                "home_team": f"Home{match_index % 8}",
                "away_team": f"Away{match_index % 8}",
                "ftr": result,
                "market_overround": 0.05 + 0.001 * (match_index % 5),
                "market_p_home": raw[0],
                "market_p_draw": raw[1],
                "market_p_away": raw[2],
            }
            for feature in PUBLIC_NUMERIC_FEATURES:
                row.setdefault(feature, float(rng.normal()))
            rows.append(row)
    return pd.DataFrame(rows)
