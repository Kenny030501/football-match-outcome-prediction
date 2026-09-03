# Market probability audit

## Build-vs-buy conclusion

**Recommendation: Use market probabilities as-is.**

The decision follows pre-specified rules across four expanding-window test seasons. A lower metric is better; negative comparison deltas favor the candidate model.

## Audit findings

- Raw market probabilities are already closely calibrated: pooled class ECE is 0.008 for home wins, 0.006 for draws, and 0.011 for away wins.
- Recalibration changes pooled log loss from 1.0163 to 1.0166; the paired confidence interval includes zero.
- Adding Elo, recent form, rest, league, and season progress worsens log loss in all four test seasons.
- The raw market's argmax rule has 0.08% draw recall. This is a class-decision limitation, not evidence that the draw probabilities themselves are uncalibrated.
- Test-season raw-market log loss stays within a narrow range, with no large aggregate drift across 2022/23-2025/26.

## Out-of-time results

| Test season | Model | Log loss | Brier | Accuracy | Macro F1 |
| --- | --- | ---: | ---: | ---: | ---: |
| 2223 | Market raw | 1.0165 | 0.6099 | 49.27% | 0.3639 |
| 2223 | Market recalibrated | 1.0177 | 0.6106 | 49.30% | 0.3640 |
| 2223 | Market + public features | 1.0242 | 0.6131 | 49.15% | 0.3636 |
| 2324 | Market raw | 1.0139 | 0.6070 | 49.42% | 0.3598 |
| 2324 | Market recalibrated | 1.0139 | 0.6070 | 49.42% | 0.3588 |
| 2324 | Market + public features | 1.0265 | 0.6099 | 49.19% | 0.3606 |
| 2425 | Market raw | 1.0208 | 0.6126 | 49.19% | 0.3661 |
| 2425 | Market recalibrated | 1.0214 | 0.6129 | 49.15% | 0.3650 |
| 2425 | Market + public features | 1.0236 | 0.6136 | 48.76% | 0.3647 |
| 2526 | Market raw | 1.0140 | 0.6079 | 50.23% | 0.3689 |
| 2526 | Market recalibrated | 1.0135 | 0.6076 | 50.27% | 0.3692 |
| 2526 | Market + public features | 1.0146 | 0.6085 | 50.04% | 0.3723 |

## Paired clustered bootstrap comparisons

| Candidate vs baseline | Metric | Delta | 95% CI | Test seasons improved |
| --- | --- | ---: | ---: | ---: |
| Market recalibrated vs Market raw | log_loss | +0.00030 | [-0.00030, +0.00090] | 2/4 |
| Market recalibrated vs Market raw | brier | +0.00022 | [-0.00018, +0.00060] | 1/4 |
| Market + public features vs Market recalibrated | log_loss | +0.00561 | [+0.00251, +0.01033] | 0/4 |
| Market + public features vs Market recalibrated | brier | +0.00173 | [+0.00087, +0.00262] | 0/4 |

## Decision-rule outcome

- Recalibration qualifies: no
- Public-feature augmentation qualifies: no
- No claim is based on one season, one subgroup, or accuracy alone.

## Where prediction is easier or harder

- Lowest league-level raw-market log loss: E0 at 0.9603.
- Highest league-level raw-market log loss: E3 at 1.0435.
- Low-confidence matches are materially harder than matches with a market favorite above 75%.
- Slice differences describe predictability; they are not evidence of profitable mispricing.

## Slice coverage

- confidence: 4 slices
- league: 5 slices
- outcome: 3 slices
- overround: 5 slices
- season: 4 slices

## Evidence boundary

- This is a third-party probability audit, not a betting strategy or profitability test.
- The primary baseline is the normalized market-average closing 1X2 price.
- Public features are computed strictly from matches completed before the current date.
- Lineups, injuries, xG, weather, and paid feeds are outside the study.
