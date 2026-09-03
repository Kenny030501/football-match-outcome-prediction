# Data source assessment

Verified on 2026-09-03.

## Decision

Football-Data.co.uk remains the primary source because it combines account-free
CSV access, complete English-league results, and market-average closing odds.
The current study narrows its audit window to 2019/20-2025/26, where the closing
market fields are consistent, and uses 2017/18-2018/19 only to warm up lagged
team state.

No alternative reviewed source simultaneously offers the same closing-odds
coverage, account-free access, reproducibility, and cross-division history.

## Current acquisition result

The production build refreshed every planned URL rather than relying on the old
cache.

| Check | Result |
| --- | ---: |
| Expected source files | 45 |
| Successfully downloaded files | 45 |
| Warm-up rows | 5,176 |
| Audit rows | 17,630 |
| Total accepted rows | 22,806 |
| Quarantined rows | 0 |
| Audit rows missing market-average closing odds | 0 |
| Audit rows missing at least one Bet365 closing quote | 2 |

Each manifest record contains the URL, retrieval time, byte size, source and
accepted row counts, status, and SHA-256 hash. Raw CSVs are excluded from Git.

## Why the scope starts in 2019/20

The provider documents fields ending in `C` as closing odds. In the reviewed
English files, `AvgCH`, `AvgCD`, and `AvgCA` are present and complete across all
five divisions beginning in 2019/20. They form a better third-party market
benchmark than one bookmaker's earlier snapshot.

The archived portfolio pipeline used Bet365 pre-closing odds over a longer
history. Ten files from 2002/03-2004/05 also contained irregular trailing fields
that caused Pandas to skip 5,158 otherwise usable rows. The new named-column
parser accepts irrelevant trailing fields and records genuine row failures in a
quarantine table instead of dropping an entire file.

## Field-quality assessment

| Field family | Assessment | Use in current study |
| --- | --- | --- |
| Match identity and final result | Medium-high for public research | Target and lagged-state updates |
| Market-average closing 1X2 odds | Best available account-free benchmark | Primary external probabilities |
| Bet365 closing 1X2 odds | Two incomplete rows | Reference only |
| Shots, cards, corners, and half-time fields | Inconsistent and post-match | Excluded |
| Static stadium geography | 2015 snapshot with 49.46% prior row coverage | Removed |

The provider disclaims correctness and does not expose stable match IDs. The
pipeline therefore validates natural-key uniqueness, result-score consistency,
odds ranges, and file hashes locally.

## Alternatives reviewed

### StatsBomb Open Data

Best free option for event-level analysis, lineups, and selected 360 data. It
has structured match and event identifiers and explicit attribution guidance.
Its open English men's Premier League coverage is too narrow to replace the
seven-season, five-division closing-odds audit.

### football-data.org

Provides a structured API and stable competition identifiers. Free access is
rate-limited and historical depth and pre-match odds require paid packages. It
is useful for current fixtures or entity reconciliation, not as the primary
reproducible source here.

### API-Football and Sportmonks

Offer broader fixtures, lineups, injuries, statistics, xG, and odds. They are
better candidates for a production application but require account-bound or
paid access and would weaken clean-clone reproducibility.

### Opta / Stats Perform

Provides professional event, historical, and player-tracking data. It is the
highest-quality commercial option reviewed but is proprietary and sales-led.

## Source policy

1. Download raw Football-Data.co.uk files at runtime.
2. Record retrieval metadata and SHA-256 hashes.
3. Parse only named fields and quarantine invalid rows.
4. Stop the production build when a required file fails or the audit row count
   changes from 17,630.
5. Re-run the complete audit after a source hash or row-count change.
6. Do not redistribute raw source files.
7. Do not add paid or event-level data unless the research question changes.

## Source links

- [Football-Data.co.uk England files](https://www.football-data.co.uk/englandm.php)
- [Football-Data.co.uk field notes](https://www.football-data.co.uk/notes.txt)
- [Football-Data.co.uk disclaimer](https://www.football-data.co.uk/disclaimer.php)
- [StatsBomb Open Data](https://github.com/hudl/open-data)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [API-Football coverage](https://www.api-football.com/coverage)
- [Sportmonks Football API](https://www.sportmonks.com/football-api/)
- [Opta Data](https://www.statsperform.com/products/opta-data/)
