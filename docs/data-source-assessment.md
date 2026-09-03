# Data source assessment

Verified on 2026-09-03.

## Decision

Keep Football-Data.co.uk as the primary free source for the long-history result
and odds study, but do not treat the current pipeline as fully reproducible yet.
Repair the early-season CSV parser, separate pre-closing from closing odds, and
remove or replace the static stadium source before extending the model.

No alternative reviewed source simultaneously offers the same long English
league history, bookmaker odds, account-free access, and a clearer schema.
Higher-quality sources improve particular dimensions but introduce narrower
coverage, account requirements, paid access, or redistribution restrictions.

## Reacquisition test

The source's England download page was active and marked updated on 2026-09-01.
A fresh endpoint probe covered five league codes (`E0`, `E1`, `E2`, `E3`, and
`EC`) for every season from 1998/99 through 2023/24.

| Check | Result |
| --- | ---: |
| Expected season-league endpoints | 130 |
| Endpoints returning CSV content | 123 |
| Files containing the current model's required headers | 107 |
| Rows with complete target and positive Bet365 1X2 odds | 54,566 |
| Rows missing at least one required value | 103 |
| Rows with non-positive required odds | 6 |
| Duplicate date-league-home-away keys in valid rows | 0 |

The data can therefore be reacquired without relying on the local cache.
However, the current pipeline reproduces only 49,408 rows because Pandas raises
parser errors on ten files from 2002/03 through 2004/05. The loader catches those
errors and silently skips the whole file. The 5,158-row difference is an
ingestion defect, not an intentional sample filter.

The earliest files do not contain Bet365 odds. The model-ready history begins in
2002/03. Conference (`EC`) coverage begins in 2005/06.

## Quality by field family

| Field family | Assessment | Main issue |
| --- | --- | --- |
| Match identity and final result | Medium-high for portfolio research | Provider disclaims correctness; no stable match ID |
| Bet365 1X2 odds | Medium | Pre-closing snapshot and one bookmaker, not a closing consensus |
| Closing and market-average odds | Medium-high from 2019/20 | Shorter history and changing bookmaker coverage |
| Shots, cards, corners, referee | Medium-low across the full panel | Missingness and definitions vary by league and season; post-match only |
| Kickoff time | Incomplete historically | Present from 2019/20 in the audited English files |
| Stadium geography | Low | Static 2015 file, historical venue errors, and 49.46% row coverage |

The source documentation says weekend odds are collected on Friday afternoons
and midweek odds on Tuesday afternoons. Columns with an added `C` denote closing
odds. Using `B365H/B365D/B365A` across all years is valid as a documented
pre-closing bookmaker snapshot, but it is not sufficient evidence for a strong
claim about closing-market efficiency.

## Stadium-source finding

The current stadium CSV is still downloadable but is dated 2015. In the current
49,408-row reproduced sample:

- only 24,438 rows have both home and away coordinates;
- coverage is 49.46%;
- 89 team names have no coordinate match;
- some venue names are historically stale, such as Tottenham's White Hart Lane
  and West Ham's Boleyn Ground.

Median imputation hides this missingness inside the model. Until a versioned,
effective-date venue table is available, travel distance should be removed from
the primary specification and retained only as an explicitly incomplete
ablation.

## Alternatives reviewed

### StatsBomb Open Data

Best free option for event-level analysis, lineups, and selected 360 data. It
has explicit publication attribution instructions and structured JSON with
stable match and event identifiers. Its open English men's Premier League
coverage currently includes only 2003/04 and 2015/16, so it cannot replace the
long-history odds panel. It is suitable for a separate match-mechanism or xG
module, not for the main market benchmark.

### football-data.org

Better structured API and competition identifiers than the CSV source. The free
tier currently covers 12 competitions with delayed scores and a 10-call-per-
minute limit. Ten seasons of history require the ML Pack Light tier, while
pre-match 1X2 odds are a separate add-on. It is useful for current fixtures and
entity reconciliation, but not a free replacement for the 2002-2024 study.

### API-Football

Broad API coverage with fixtures, lineups, injuries, statistics, and pre-match
odds. The free plan is limited to 100 requests per day and to selected seasons;
paid access improves request volume. It is a possible source for a smaller
point-in-time pre-match feature extension, provided fetch timestamps and raw
responses are versioned. Provider coverage claims are not an independent data-
accuracy audit.

### Sportmonks

Commercial API with lineups, statistics, xG, predictions, and odds in a uniform
schema. The provider advertises human verification and broad league coverage.
It is better suited to a production-style application than a zero-cost public
portfolio reproduction.

### Opta / Stats Perform

Highest-quality professional option reviewed for event, historical, and player-
tracking data. It is proprietary and sales-led, so it would materially reduce
the reproducibility of a public student portfolio.

## Recommended source design

1. Use Football-Data.co.uk results and odds for the reproducible core.
2. Store a download manifest with URL, retrieval timestamp, byte size, and
   SHA-256 hash instead of committing raw files.
3. Parse only named columns and explicitly quarantine malformed rows; never skip
   a whole season-league file silently.
4. Use 2002/03 onward for the long-run structural study and label the Bet365
   fields as pre-closing snapshots.
5. Use 2019/20 onward with `AvgCH/AvgCD/AvgCA` for the primary closing-market
   comparison.
6. Remove travel distance from the main model until venue coverage and effective
   dates are fixed.
7. Add StatsBomb only if the project deliberately expands into event-level
   explanation; do not merge it merely to make the dataset look richer.

## Source links

- [Football-Data.co.uk England files](https://www.football-data.co.uk/englandm.php)
- [Football-Data.co.uk field notes](https://www.football-data.co.uk/notes.txt)
- [Football-Data.co.uk disclaimer](https://www.football-data.co.uk/disclaimer.php)
- [StatsBomb Open Data](https://github.com/hudl/open-data)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org pricing](https://www.football-data.org/pricing)
- [API-Football coverage](https://www.api-football.com/coverage)
- [API-Football pricing](https://www.api-football.com/pricing)
- [Sportmonks Football API](https://www.sportmonks.com/football-api/)
- [Opta Data](https://www.statsperform.com/products/opta-data/)
