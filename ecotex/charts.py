"""Score breakdown chart (matplotlib, no pyplot global state, safe for concurrent users)."""

from __future__ import annotations

from typing import Any

from matplotlib.figure import Figure

from .process import fmt, score_parts

# Okabe-Ito palette: readable for people with color-vision deficiency.
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9"]


def score_breakdown_figure(options: list[dict[str, Any]]) -> Figure:
    """Stacked horizontal bars: how each option's Eco Score is made up."""
    count = max(len(options), 1)
    fig = Figure(figsize=(8.2, 1.9 + 0.85 * count), dpi=110, facecolor="white")
    ax = fig.subplots()
    ax.set_facecolor("white")

    labels: list[str] = []
    for opt in options:
        labels.append(f"#{opt['rank']}  {opt['DyeType']}\n{opt['Fiber']} · {opt['Color']}")

    legend_handles = {}
    for row_index, opt in enumerate(options):
        left = 0.0
        for part_index, (label, points, _maximum) in enumerate(score_parts(opt)):
            bar = ax.barh(
                row_index,
                points,
                left=left,
                color=PALETTE[part_index % len(PALETTE)],
                edgecolor="white",
                linewidth=1.2,
                height=0.62,
            )
            legend_handles.setdefault(label, bar)
            if points >= 5:
                ax.text(
                    left + points / 2,
                    row_index,
                    fmt(points),
                    ha="center",
                    va="center",
                    fontsize=8.5,
                    color="white" if part_index in (0, 3, 4) else "#1a1a1a",
                    fontweight="bold",
                )
            left += points
        ax.text(left + 1.2, row_index, f"{fmt(opt['Eco Score'])}", va="center", fontsize=11, fontweight="bold", color="#1a1a1a")

    ax.set_yticks(range(len(options)))
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_xlabel("Eco Score (out of 100)", fontsize=10)
    ax.set_title("What makes up each option's Eco Score", fontsize=12, fontweight="bold", loc="left", pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)

    if legend_handles:
        ax.legend(
            legend_handles.values(),
            legend_handles.keys(),
            loc="upper center",
            bbox_to_anchor=(0.5, -0.22),
            ncol=3,
            frameon=False,
            fontsize=8.5,
        )
    fig.tight_layout()
    return fig
