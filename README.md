# Can Models Beat the Market?

## A leakage-audited football forecasting study

This repository is a reproducible audit and portfolio reconstruction of a 2025
University of Pennsylvania CIS 5450 team project by Lucas Qu, Leo Lin, and
Hongru Da.

The project asks a deliberately narrow question:

> How much of an English football match outcome can be predicted using only
> information available before kickoff, and do simple public features add value
> beyond bookmaker prices?

The main result is negative but useful. Once same-match information is removed
and the holdout is moved forward in time, the enriched models do not beat the
bookmaker-favorite rule on accuracy or log loss. The portfolio value of the
project is therefore its research design, leakage audit, temporal evaluation,
and willingness to report a failed hypothesis rather than a larger headline
metric.

## Executive result

- 49,408 matches in the currently reproduced sample
- Training period: August 2002 to October 2020
- Chronological holdout: October 2020 to May 2024
- Best accuracy and log loss: bookmaker favorite
- Best macro F1: random forest using pre-match features
- Defensible conclusion: the added public features contain limited incremental
  signal beyond the selected bookmaker odds in this specification

## Why this repository has two versions

The archived course notebook reported 54-56% accuracy for Random Forest and MLP
models. Its advanced-model feature table included same-match statistics and a
`HighScoring` variable derived from final goals. Those figures demonstrate model
fitting, but they are not valid pre-match forecasts.

The portfolio pipeline in `src/portfolio_pipeline.py` changes the research
design:

- Matches are sorted chronologically before splitting.
- The most recent 20% of observations form the holdout set.
- Scalers and imputers are fitted on training data only.
- Same-match goals, shots, cards, corners, and other post-kickoff information
  are excluded.
- Features are limited to bookmaker odds, normalized implied probabilities,
  static travel distance, league, and five-match lagged form.

The output-stripped team notebook is retained only for provenance and carries a
leakage warning at the top.

## Corrected holdout results

| Model | Accuracy | Macro F1 | Log loss |
| --- | ---: | ---: | ---: |
| Always home win | 43.05% | 20.06% | - |
| Bookmaker favorite | **49.63%** | 36.72% | **1.017** |
| Logistic regression, odds only | 46.06% | 42.97% | 1.043 |
| Logistic regression, all pre-match features | 45.78% | 42.42% | 1.043 |
| Random forest, all pre-match features | 46.28% | **43.12%** | 1.044 |
| MLP, all pre-match features | 49.16% | 37.11% | 1.021 |

## Data evidence boundary

The primary match source is
[Football-Data.co.uk](https://www.football-data.co.uk/englandm.php). The raw CSV
files are downloaded at runtime and excluded from Git.

Important qualifications:

- Bet365 `B365H/B365D/B365A` fields are documented as pre-closing odds, not a
  consistent closing-market consensus. Closing fields become available in the
  source files only from 2019/20 onward.
- The provider's column set changes materially across seasons and leagues.
- Several 2002/03-2004/05 files contain irregular trailing fields that the
  current Pandas reader rejects, causing the current pipeline to omit 5,158
  otherwise usable rows.
- The 2015 stadium reference covers only 49.46% of the currently reproduced
  match rows and is not reliable for historical venue changes. Travel distance
  should be treated as an experimental feature, not a core result.
- The source site states that the files are free, but the reviewed pages do not
  provide a clear open-data license or guarantee correctness. This repository
  does not redistribute the raw files.

The full source audit and replacement options are documented in
[`docs/data-source-assessment.md`](docs/data-source-assessment.md).

## Ownership and attribution

The original notebook is a collective team artifact. The public repository does
not contain a contemporaneous task log that would support assigning individual
course sections to specific members.

The leakage-audited portfolio reconstruction is maintained by Hongru Da. See
[`CONTRIBUTIONS.md`](CONTRIBUTIONS.md) and [`NOTICE.md`](NOTICE.md) for the
verified attribution boundary.

## Repository map

| Path | Purpose |
| --- | --- |
| `src/portfolio_pipeline.py` | Corrected pre-match-only data and modeling pipeline |
| `results/portfolio_metrics.json` | Reproduced holdout metrics |
| `notebooks/original-team-notebook.ipynb` | Output-stripped team archive with a leakage warning |
| `docs/data-source-assessment.md` | Reacquisition, quality, licensing, and source alternatives |
| `CONTRIBUTIONS.md` | Team and portfolio-reconstruction attribution boundary |
| `NOTICE.md` | Reuse notice |

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/portfolio_pipeline.py
```

Match CSVs are cached under `data/raw/`, which is excluded from version control.
The current command is reproducible for the reported 49,408-row result when the
existing parser accepts the source files. Repairing the early-season parser and
adding a download manifest are the next data-engineering priorities.

## Limitations and next validation step

- The holdout is one chronological split rather than a rolling-origin study.
- Bookmaker odds are strong information aggregates and dominate the small set
  of engineered features.
- The current odds baseline is one bookmaker's pre-closing snapshot, not the
  complete closing market.
- Team-form features do not capture injuries, lineups, managers, transfers, or
  expected goals.
- Accuracy is not a profitability test; no betting strategy or transaction
  economics are claimed.

The next version should first repair ingestion, remove or replace the stadium
feature, and add rolling-origin evaluation with paired uncertainty intervals.
