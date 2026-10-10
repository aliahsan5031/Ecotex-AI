"""Turn a Recommendation into the pieces the UI shows (Markdown, table, label)."""

from __future__ import annotations

import pandas as pd

from .engine import Recommendation
from .process import explain_many, fmt, process_steps

TABLE_COLUMNS = [
    "Rank",
    "Fiber",
    "Dye class",
    "Color",
    "Shade",
    "Eco score",
    "Rating",
    "EPA",
    "Temp (°C)",
    "pH",
    "NaCl",
]

DISCLAIMER = (
    "Scores come from the bundled dataset, which looks illustrative rather than measured. "
    "The process outline lists dataset values only (no times, auxiliaries or after-treatment details). "
    "Validate every recipe in a lab before production."
)


def empty_table() -> pd.DataFrame:
    return pd.DataFrame(columns=TABLE_COLUMNS)


def options_table(rec: Recommendation) -> pd.DataFrame:
    rows = [
        {
            "Rank": o["rank"],
            "Fiber": o["Fiber"],
            "Dye class": o["DyeType"],
            "Color": o["Color"],
            "Shade": o["ShadeLevel"],
            "Eco score": float(o["Eco Score"]),
            "Rating": o["Eco Rating"],
            "EPA": o["EPA"],
            "Temp (°C)": fmt(o["Temperature"]),
            "pH": fmt(o["pH"]),
            "NaCl": fmt(o["NaCl Required"]),
        }
        for o in rec.options
    ]
    return pd.DataFrame(rows, columns=TABLE_COLUMNS) if rows else empty_table()


def best_score_label(rec: Recommendation) -> str:
    if not rec.ok:
        return ""
    best = rec.options[0]
    return f"{fmt(best['Eco Score'])} / 100 · {best['Eco Rating']}"


def status_markdown(rec: Recommendation) -> str:
    if rec.status == "ok":
        found = rec.parsed.describe() if rec.parsed else ""
        shown = len(rec.options)
        plural = "s" if rec.matches != 1 else ""
        tail = "showing all of them." if shown == rec.matches else f"showing the top {shown}."
        lines = [
            f"✅ **Found {rec.matches} matching recipe{plural}**, {tail}",
            f"Understood: {found}",
        ]
        lines += [f"⚠️ {n}" for n in rec.notes]
        return "\n\n".join(lines)
    icon = {"off_topic": "🌿", "no_data": "ℹ️", "empty": "✏️"}.get(rec.status, "⚠️")
    extra = [f"⚠️ {n}" for n in rec.notes]
    return "\n\n".join([f"{icon} {rec.message}", *extra])


def _parameter_table(opt: dict) -> str:
    rows = [
        ("Fiber", opt["Fiber"]),
        ("Dye class", opt["DyeType"]),
        ("Color", opt["Color"]),
        ("Shade level", opt["ShadeLevel"]),
        ("Dye method", opt["Dye Method"]),
        ("Temperature", f"{fmt(opt['Temperature'])} °C"),
        ("Liquor ratio", opt["LiquorRatio"]),
        ("Dye concentration", fmt(opt["Dye Concentration"])),
        ("Shade %", fmt(opt["Shade %"])),
        ("pH", fmt(opt["pH"])),
        ("NaCl required", fmt(opt["NaCl Required"])),
        ("Dye residues", fmt(opt["Dye Residues"])),
        ("Dye tenacity", opt["Dye Tenacity"]),
        ("EPA compliant", opt["EPA"]),
    ]
    body = "\n".join(f"| {k} | {v} |" for k, v in rows)
    return f"| Parameter | Value |\n|---|---|\n{body}"


def options_markdown(rec: Recommendation) -> str:
    """Details for every option: explanation, parameters and process outline."""
    if not rec.ok:
        return ""
    explanations = explain_many(rec.options)
    blocks: list[str] = []
    for opt, (text, by_model) in zip(rec.options, explanations):
        title = (
            f"### Option {opt['rank']}: {opt['DyeType']} dye on {str(opt['Fiber']).lower()}, "
            f"{str(opt['Color']).lower()} ({fmt(opt['Eco Score'])}/100)"
        )
        if opt["rank"] == 1:
            title += "  ⭐ best"
        label = "Why (AI summary)" if by_model else "Why"
        steps = "\n".join(f"{i}. {s}" for i, s in enumerate(process_steps(opt), start=1))
        blocks.append(
            f"{title}\n\n**{label}:** {text}\n\n{_parameter_table(opt)}\n\n**Process outline**\n\n{steps}"
        )
    return "\n\n---\n\n".join(blocks)
