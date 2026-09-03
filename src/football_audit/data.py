from __future__ import annotations

import csv
import hashlib
import io
import time
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import requests

from football_audit.config import (
    ALL_SEASONS,
    AUDIT_ODDS_COLUMNS,
    AUDIT_SEASONS,
    IDENTITY_COLUMNS,
    LEAGUES,
    RAW_DIR,
    REFERENCE_ODDS_COLUMNS,
    SOURCE_URL,
)


def _download(url: str, attempts: int = 3) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(
                url,
                timeout=60,
                headers={"User-Agent": "football-market-audit/0.1"},
            )
            response.raise_for_status()
            if b"," not in response.content[:1000] or b"<html" in response.content[:1000].lower():
                raise ValueError("response is not a CSV file")
            return response.content
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(1 + attempt)
    raise RuntimeError(f"download failed after {attempts} attempts: {last_error}")


def acquire_sources(
    refresh: bool = False,
) -> tuple[list[dict[str, object]], dict[tuple[str, str], bytes]]:
    manifest: list[dict[str, object]] = []
    payloads: dict[tuple[str, str], bytes] = {}
    for season in ALL_SEASONS:
        for league in LEAGUES:
            url = SOURCE_URL.format(season=season, league=league)
            path = RAW_DIR / season / f"{league}.csv"
            status = "cached"
            error = ""
            try:
                if refresh or not path.exists():
                    content = _download(url)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                    status = "downloaded"
                else:
                    content = path.read_bytes()
                payloads[(season, league)] = content
                retrieved_at = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
                sha256 = hashlib.sha256(content).hexdigest()
                byte_size = len(content)
            except (OSError, RuntimeError) as exc:
                content = b""
                retrieved_at = datetime.now(UTC).isoformat()
                sha256 = ""
                byte_size = 0
                status = "download_error"
                error = str(exc)
            manifest.append(
                {
                    "season": season,
                    "league": league,
                    "url": url,
                    "retrieved_at_utc": retrieved_at,
                    "sha256": sha256,
                    "byte_size": byte_size,
                    "status": status,
                    "error": error,
                }
            )
    return manifest, payloads


def _parse_date(value: str) -> pd.Timestamp:
    parsed = pd.to_datetime(value, dayfirst=True, errors="raise")
    return pd.Timestamp(parsed).normalize()


def _valid_result(result: str, home_goals: int, away_goals: int) -> bool:
    expected = "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D"
    return result == expected


def parse_source(
    content: bytes,
    season: str,
    league: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]], int]:
    text = content.decode("latin-1")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as error:
        raise ValueError("empty CSV") from error
    header = [column.lstrip("\ufeff").removeprefix("ï»¿") for column in header]
    index = {column: position for position, column in enumerate(header)}
    required = set(IDENTITY_COLUMNS)
    if season in AUDIT_SEASONS:
        required.update(AUDIT_ODDS_COLUMNS)
    missing_columns = sorted(required - set(index))
    if missing_columns:
        raise ValueError(f"missing required columns: {missing_columns}")

    accepted: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    source_rows = 0
    for line_number, row in enumerate(reader, start=2):
        if not row or not any(value.strip() for value in row):
            continue
        source_rows += 1
        reason = ""
        try:
            max_required_index = max(index[column] for column in required)
            if len(row) <= max_required_index:
                raise ValueError("row has fewer fields than required")
            values = {
                column: row[position].strip()
                for column, position in index.items()
                if position < len(row)
            }
            if any(not values.get(column, "") for column in IDENTITY_COLUMNS):
                raise ValueError("missing identity or result value")
            match_date = _parse_date(values["Date"])
            home_goals = int(float(values["FTHG"]))
            away_goals = int(float(values["FTAG"]))
            result = values["FTR"]
            if result not in {"H", "D", "A"}:
                raise ValueError("invalid FTR")
            if not _valid_result(result, home_goals, away_goals):
                raise ValueError("FTR does not match final score")

            audit_odds: list[float] = []
            if season in AUDIT_SEASONS:
                audit_odds = [float(values[column]) for column in AUDIT_ODDS_COLUMNS]
                if not all(np.isfinite(value) and value > 1 for value in audit_odds):
                    raise ValueError("invalid average closing odds")
            else:
                audit_odds = [np.nan, np.nan, np.nan]

            reference_odds = []
            for column in REFERENCE_ODDS_COLUMNS:
                raw = values.get(column, "")
                try:
                    value = float(raw)
                    reference_odds.append(value if np.isfinite(value) and value > 1 else np.nan)
                except (TypeError, ValueError):
                    reference_odds.append(np.nan)

            accepted.append(
                {
                    "season": season,
                    "league": league,
                    "match_date": match_date,
                    "kickoff_time": values.get("Time", ""),
                    "home_team": values["HomeTeam"],
                    "away_team": values["AwayTeam"],
                    "ftr": result,
                    "fthg": home_goals,
                    "ftag": away_goals,
                    "avg_close_home": audit_odds[0],
                    "avg_close_draw": audit_odds[1],
                    "avg_close_away": audit_odds[2],
                    "b365_close_home": reference_odds[0],
                    "b365_close_draw": reference_odds[1],
                    "b365_close_away": reference_odds[2],
                    "is_audit": season in AUDIT_SEASONS,
                }
            )
        except (KeyError, TypeError, ValueError) as error:
            reason = str(error)
        if reason:
            quarantine.append(
                {
                    "season": season,
                    "league": league,
                    "source_line": line_number,
                    "reason": reason,
                }
            )
    return accepted, quarantine, source_rows


def load_sources(
    manifest: list[dict[str, object]],
    payloads: dict[tuple[str, str], bytes],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    matches: list[dict[str, object]] = []
    quarantine: list[dict[str, object]] = []
    manifest_by_key = {(row["season"], row["league"]): row for row in manifest}
    for season in ALL_SEASONS:
        for league in LEAGUES:
            key = (season, league)
            manifest_row = manifest_by_key[key]
            content = payloads.get(key)
            if content is None:
                manifest_row.update({"source_rows": 0, "accepted_rows": 0, "quarantined_rows": 0})
                continue
            try:
                accepted, rejected, source_rows = parse_source(content, season, league)
                matches.extend(accepted)
                quarantine.extend(rejected)
                manifest_row.update(
                    {
                        "source_rows": source_rows,
                        "accepted_rows": len(accepted),
                        "quarantined_rows": len(rejected),
                    }
                )
            except ValueError as error:
                manifest_row.update(
                    {
                        "status": "parse_error",
                        "error": str(error),
                        "source_rows": 0,
                        "accepted_rows": 0,
                        "quarantined_rows": 0,
                    }
                )

    frame = pd.DataFrame(matches)
    if frame.empty:
        raise RuntimeError("no source rows were accepted")
    natural_key = ["league", "match_date", "home_team", "away_team"]
    duplicated = frame.duplicated(natural_key, keep=False)
    if duplicated.any():
        examples = frame.loc[duplicated, natural_key].head(5).to_dict("records")
        raise ValueError(f"duplicate natural match keys: {examples}")
    frame = frame.sort_values(["match_date", "league", "home_team", "away_team"]).reset_index(
        drop=True
    )
    return frame, pd.DataFrame(manifest), pd.DataFrame(quarantine)
