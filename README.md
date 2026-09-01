# Football Match Outcome Prediction

A reproducible audit and portfolio reconstruction of a University of Pennsylvania CIS 5450 team project by Lucas Qu, Leo Lin, and Hongru Da.

The project combines more than 49,000 English-league matches, bookmaker odds, static stadium geography, and lagged team-form features. The public portfolio pipeline focuses on a strict question: **how much of match outcome can be predicted using only information available before kickoff?**

## Why this repository has two versions

The archived course notebook reported 54-56% accuracy for Random Forest and MLP models, but its advanced-model feature table included same-match statistics and a `HighScoring` variable derived from final goals. Those results are useful as an example of classification and model fitting, but they are not valid pre-match forecasts.

For the public portfolio version, `src/portfolio_pipeline.py` corrects the research design:

- Matches are sorted chronologically before splitting.
- The most recent 20% of observations form the holdout set.
- Scalers and imputers are fitted on training data only.
- Same-match goals, shots, cards, corners, and other post-kickoff information are excluded.
- Features are limited to bookmaker odds, normalized implied probabilities, static travel distance, league, and five-match lagged form.

## Corrected holdout results

The final sample contains 49,408 matches. Training runs from August 2002 through October 2020; the holdout runs from October 2020 through May 2024.

| Model | Accuracy | Macro F1 | Log loss |
| --- | ---: | ---: | ---: |
| Always home win | 43.05% | 20.06% | - |
| Bookmaker favorite | **49.63%** | 36.72% | **1.017** |
| Logistic regression, odds only | 46.06% | 42.97% | 1.043 |
| Logistic regression, all pre-match features | 45.78% | 42.42% | 1.043 |
| Random forest, all pre-match features | 46.28% | **43.12%** | 1.044 |
| MLP, all pre-match features | 49.16% | 37.11% | 1.021 |

The negative result matters: the enriched models did not beat the simple bookmaker-favorite rule on accuracy or log loss. The strongest defensible conclusion is that public pre-match features add limited incremental signal beyond market odds in this specification.

## Repository map

| Path | Purpose |
| --- | --- |
| `src/portfolio_pipeline.py` | Corrected pre-match-only data and modeling pipeline |
| `results/portfolio_metrics.json` | Reproduced holdout metrics |
| `notebooks/original-team-notebook.ipynb` | Output-stripped archive of the original team notebook, with a leakage warning |
| `NOTICE.md` | Team attribution and reuse terms |

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/portfolio_pipeline.py
```

Match CSVs are downloaded from Football-Data.co.uk and cached under `data/raw/`, which is excluded from version control. The static stadium file is downloaded from the source used in the original course project.

## Limitations

- The holdout is one chronological split rather than a rolling-origin evaluation.
- Bookmaker odds are strong market aggregates and may dominate the small set of engineered features.
- The stadium reference file is historical and has incomplete coverage for renamed or newly promoted clubs.
- Team-form features are deliberately simple and do not capture injuries, lineups, managers, transfers, or expected goals.
- Accuracy alone is not a profitability test; no betting strategy or transaction economics are evaluated.

The archived notebook remains a team artifact. No license is granted for reuse of that material.
