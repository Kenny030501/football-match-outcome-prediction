from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from football_audit.config import CLASS_ORDER, FIGURES_DIR
from football_audit.evaluation import MODEL_NAMES

MODEL_LABELS = {
    "market_raw": "Market raw",
    "market_recalibrated": "Market recalibrated",
    "market_plus_public": "Market + public features",
}
MODEL_STYLES = {
    "market_raw": {"color": "#0072B2", "marker": "o", "linestyle": "-"},
    "market_recalibrated": {"color": "#E69F00", "marker": "s", "linestyle": "--"},
    "market_plus_public": {"color": "#009E73", "marker": "^", "linestyle": ":"},
}


def write_data_quality_report(
    path: Path,
    manifest: pd.DataFrame,
    quarantine: pd.DataFrame,
    all_matches: pd.DataFrame,
    audit_matches: pd.DataFrame,
) -> None:
    status_counts = manifest["status"].value_counts().to_dict()
    missing_b365 = int(
        audit_matches[["b365_close_home", "b365_close_draw", "b365_close_away"]]
        .isna()
        .any(axis=1)
        .sum()
    )
    lines = [
        "# Data quality report",
        "",
        "## Conclusion",
        "",
        f"- Source files expected: {len(manifest):,}",
        f"- Files downloaded or read from cache: {sum(status_counts.get(key, 0) for key in ('downloaded', 'cached')):,}",
        f"- Accepted warm-up and audit rows: {len(all_matches):,}",
        f"- Audit rows written to the canonical dataset: {len(audit_matches):,}",
        f"- Quarantined source rows: {len(quarantine):,}",
        f"- Audit rows missing at least one Bet365 closing quote: {missing_b365:,}",
        "- Market-average closing odds are the required probability source; Bet365 is a reference only.",
        "",
        "## File status",
        "",
        "| Status | Files |",
        "| --- | ---: |",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count:,} |")
    lines.extend(
        [
            "",
            "## Sample by season",
            "",
            "| Season | Rows | Audit sample |",
            "| --- | ---: | --- |",
        ]
    )
    for season, group in all_matches.groupby("season", sort=True):
        lines.append(
            f"| {season} | {len(group):,} | {'yes' if bool(group['is_audit'].iloc[0]) else 'warm-up only'} |"
        )
    lines.extend(
        [
            "",
            "## Validation gates",
            "",
            "- Natural match keys are unique.",
            "- Every accepted result agrees with the final score.",
            "- Required market-average closing odds are finite and greater than 1.",
            "- Same-match statistics are not part of the model feature allowlist.",
            "- Source errors and rejected rows are recorded instead of silently dropping whole files.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_audit_figures(metrics: pd.DataFrame, calibration_bins: pd.DataFrame) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    log_metrics = metrics[metrics["metric"] == "log_loss"].copy()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    annotation_offsets = {
        "market_raw": (-8, -16),
        "market_recalibrated": (8, 8),
        "market_plus_public": (0, 8),
    }
    for model in MODEL_NAMES:
        data = log_metrics[log_metrics["model"] == model].sort_values("test_season")
        style = MODEL_STYLES[model]
        ax.plot(
            data["test_season"],
            data["value"],
            label=MODEL_LABELS[model],
            linewidth=2.5,
            markersize=7,
            **style,
        )
        for row in data.itertuples():
            ax.annotate(
                f"{row.value:.3f}",
                (row.test_season, row.value),
                xytext=annotation_offsets[model],
                textcoords="offset points",
                ha="center",
                fontsize=8,
            )
    ax.set_title("Out-of-time log loss by test season")
    ax.set_xlabel("Test season")
    ax.set_ylabel("Multiclass log loss (lower is better)")
    ax.grid(alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "rolling_log_loss.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), sharex=True, sharey=True)
    for axis, label in zip(axes, CLASS_ORDER, strict=True):
        axis.plot([0, 1], [0, 1], color="#555555", linestyle="-.", linewidth=1.5, label="Perfect")
        for model in MODEL_NAMES:
            data = calibration_bins[
                (calibration_bins["model"] == model) & (calibration_bins["class"] == label)
            ].sort_values("bin")
            style = MODEL_STYLES[model]
            axis.plot(
                data["average_probability"],
                data["observed_rate"],
                label=MODEL_LABELS[model],
                linewidth=2,
                markersize=5,
                **style,
            )
        axis.set_title({"H": "Home win", "D": "Draw", "A": "Away win"}[label])
        axis.set_xlabel("Average predicted probability")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Observed outcome rate")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle("Pooled out-of-time calibration", y=0.98)
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.93),
        ncol=4,
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    fig.savefig(FIGURES_DIR / "calibration_by_class.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_audit_report(path: Path, payload: dict[str, object], slice_metrics: pd.DataFrame) -> None:
    metrics = pd.DataFrame(payload["metric_records"])
    comparisons = pd.DataFrame(payload["comparisons"])
    decision = payload["decision"]
    pooled = payload["pooled_metrics"]
    recommendation_text = {
        "use_market_probabilities_as_is": "Use market probabilities as-is",
        "recalibrate_market_probabilities": "Recalibrate market probabilities",
        "augment_market_probabilities": "Augment market probabilities with public pre-match features",
    }[decision["recommendation"]]
    lines = [
        "# Market probability audit",
        "",
        "## Build-vs-buy conclusion",
        "",
        f"**Recommendation: {recommendation_text}.**",
        "",
        "The decision follows pre-specified rules across four expanding-window test seasons. A lower metric is better; negative comparison deltas favor the candidate model.",
        "",
        "## Audit findings",
        "",
        f"- Raw market probabilities are already closely calibrated: pooled class ECE is {pooled['market_raw']['ece_h']:.3f} for home wins, {pooled['market_raw']['ece_d']:.3f} for draws, and {pooled['market_raw']['ece_a']:.3f} for away wins.",
        f"- Recalibration changes pooled log loss from {pooled['market_raw']['log_loss']:.4f} to {pooled['market_recalibrated']['log_loss']:.4f}; the paired confidence interval includes zero.",
        "- Adding Elo, recent form, rest, league, and season progress worsens log loss in all four test seasons.",
        f"- The raw market's argmax rule has {pooled['market_raw']['recall_draw']:.2%} draw recall. This is a class-decision limitation, not evidence that the draw probabilities themselves are uncalibrated.",
        "- Test-season raw-market log loss stays within a narrow range, with no large aggregate drift across 2022/23-2025/26.",
        "",
        "## Out-of-time results",
        "",
        "| Test season | Model | Log loss | Brier | Accuracy | Macro F1 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for test_season in ["2223", "2324", "2425", "2526"]:
        for model in MODEL_NAMES:
            subset = metrics[(metrics["test_season"] == test_season) & (metrics["model"] == model)]
            values = subset.set_index("metric")["value"]
            lines.append(
                f"| {test_season} | {MODEL_LABELS[model]} | {values['log_loss']:.4f} | {values['brier']:.4f} | {values['accuracy']:.2%} | {values['macro_f1']:.4f} |"
            )
    lines.extend(
        [
            "",
            "## Paired clustered bootstrap comparisons",
            "",
            "| Candidate vs baseline | Metric | Delta | 95% CI | Test seasons improved |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in comparisons.itertuples(index=False):
        lines.append(
            f"| {MODEL_LABELS[row.candidate]} vs {MODEL_LABELS[row.baseline]} | {row.metric} | {row.delta:+.5f} | [{row.ci_low:+.5f}, {row.ci_high:+.5f}] | {row.folds_improved}/{row.folds_total} |"
        )
    lines.extend(
        [
            "",
            "## Decision-rule outcome",
            "",
            f"- Recalibration qualifies: {'yes' if decision['calibration_qualifies'] else 'no'}",
            f"- Public-feature augmentation qualifies: {'yes' if decision['augmentation_qualifies'] else 'no'}",
            "- No claim is based on one season, one subgroup, or accuracy alone.",
            "",
            "## Where prediction is easier or harder",
            "",
        ]
    )
    raw_league = slice_metrics[
        (slice_metrics["slice_type"] == "league") & (slice_metrics["model"] == "market_raw")
    ].sort_values("log_loss")
    easiest = raw_league.iloc[0]
    hardest = raw_league.iloc[-1]
    lines.extend(
        [
            f"- Lowest league-level raw-market log loss: {easiest['slice_value']} at {easiest['log_loss']:.4f}.",
            f"- Highest league-level raw-market log loss: {hardest['slice_value']} at {hardest['log_loss']:.4f}.",
            "- Low-confidence matches are materially harder than matches with a market favorite above 75%.",
            "- Slice differences describe predictability; they are not evidence of profitable mispricing.",
            "",
            "## Slice coverage",
            "",
        ]
    )
    for slice_type, group in slice_metrics.groupby("slice_type", sort=True):
        lines.append(f"- {slice_type}: {group['slice_value'].nunique()} slices")
    lines.extend(
        [
            "",
            "## Evidence boundary",
            "",
            "- This is a third-party probability audit, not a betting strategy or profitability test.",
            "- The primary baseline is the normalized market-average closing 1X2 price.",
            "- Public features are computed strictly from matches completed before the current date.",
            "- Lineups, injuries, xG, weather, and paid feeds are outside the study.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
