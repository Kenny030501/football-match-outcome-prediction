from __future__ import annotations

from football_audit.data import parse_source

HEADER = "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,AvgCH,AvgCD,AvgCA,B365CH,B365CD,B365CA"


def test_parser_accepts_named_fields_with_irregular_trailing_columns() -> None:
    content = (
        HEADER
        + "\nE0,01/08/2019,15:00,Alpha,Beta,2,1,H,1.90,3.50,4.20,1.88,3.40,4.00,extra,extra\n"
    ).encode("latin-1")
    accepted, quarantine, source_rows = parse_source(content, "1920", "E0")
    assert source_rows == 1
    assert len(accepted) == 1
    assert quarantine == []
    assert accepted[0]["home_team"] == "Alpha"


def test_parser_quarantines_inconsistent_result() -> None:
    content = (
        HEADER + "\nE0,01/08/2019,15:00,Alpha,Beta,0,1,H,1.90,3.50,4.20,1.88,3.40,4.00\n"
    ).encode("latin-1")
    accepted, quarantine, source_rows = parse_source(content, "1920", "E0")
    assert source_rows == 1
    assert accepted == []
    assert quarantine[0]["reason"] == "FTR does not match final score"


def test_warmup_rows_do_not_require_closing_odds() -> None:
    header = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR"
    content = (header + "\nE0,01/08/2017,Alpha,Beta,0,0,D\n").encode("latin-1")
    accepted, quarantine, _ = parse_source(content, "1718", "E0")
    assert len(accepted) == 1
    assert quarantine == []
