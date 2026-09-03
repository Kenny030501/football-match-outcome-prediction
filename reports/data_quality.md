# Data quality report

## Conclusion

- Source files expected: 45
- Files downloaded or read from cache: 45
- Accepted warm-up and audit rows: 22,806
- Audit rows written to the canonical dataset: 17,630
- Quarantined source rows: 0
- Audit rows missing at least one Bet365 closing quote: 2
- Market-average closing odds are the required probability source; Bet365 is a reference only.

## File status

| Status | Files |
| --- | ---: |
| downloaded | 45 |

## Sample by season

| Season | Rows | Audit sample |
| --- | ---: | --- |
| 1718 | 2,588 | warm-up only |
| 1819 | 2,588 | warm-up only |
| 1920 | 2,223 | yes |
| 2021 | 2,513 | yes |
| 2122 | 2,542 | yes |
| 2223 | 2,588 | yes |
| 2324 | 2,588 | yes |
| 2425 | 2,588 | yes |
| 2526 | 2,588 | yes |

## Validation gates

- Natural match keys are unique.
- Every accepted result agrees with the final score.
- Required market-average closing odds are finite and greater than 1.
- Same-match statistics are not part of the model feature allowlist.
- Source errors and rejected rows are recorded instead of silently dropping whole files.
