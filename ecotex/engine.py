"""Filter, rank and pick the top dye recipes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .data import get_dataset
from .query import LOW_TEMPERATURE_MAX_C, ParsedQuery, parse_query

TOP_N = 3

OFF_TOPIC_MESSAGE = (
    "I'm EcoTex AI, a sustainability advisor for textile dyeing. I can help with fabric dyeing, "
    "dye recipes and eco-compliance, but not with other topics. "
    "Try something like: *eco-friendly dye for red cotton*."
)


@dataclass
class Recommendation:
    """Result of one query.

    status is one of: ``ok``, ``empty``, ``off_topic``, ``no_data``.
    """

    status: str
    message: str = ""
    options: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    parsed: ParsedQuery | None = None
    matches: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _isin(df: pd.DataFrame, column: str, values: list[str]) -> pd.Series:
    wanted = {v.lower() for v in values}
    return df[column].str.lower().isin(wanted)


def _available(df: pd.DataFrame, column: str) -> str:
    return ", ".join(sorted(df[column].unique()))


def _rank(df: pd.DataFrame) -> pd.DataFrame:
    """Best Eco Score first. Ties: EPA compliant, then lower temperature, then fewer residues.

    The Eco Score already contains the EPA points, so EPA is not added a second time.
    """
    ranked = df.assign(_epa=(df["EPA"].str.lower() == "yes").astype(int))
    ranked = ranked.sort_values(
        by=["Eco Score", "_epa", "Temperature", "Dye Residues"],
        ascending=[False, False, True, True],
        kind="mergesort",
    )
    return ranked.drop(columns="_epa")


def _pick_diverse(ranked: pd.DataFrame, n: int, key_columns: list[str]) -> pd.DataFrame:
    """Prefer different dye classes in the top n, then fill up by rank."""
    chosen: list[int] = []
    seen: set[tuple] = set()
    for idx, row in ranked.iterrows():
        key = tuple(row[c] for c in key_columns)
        if key not in seen:
            seen.add(key)
            chosen.append(idx)
        if len(chosen) == n:
            break
    if len(chosen) < n:
        for idx in ranked.index:
            if idx not in chosen:
                chosen.append(idx)
            if len(chosen) == n:
                break
    # Keep the best option first.
    return ranked.loc[chosen].sort_values("Eco Score", ascending=False, kind="mergesort")


def recommend(query: str, df: pd.DataFrame | None = None, top_n: int = TOP_N) -> Recommendation:
    """Answer a free-text question with the best matching recipes."""
    data = df if df is not None else get_dataset()
    text = (query or "").strip()
    if not text:
        return Recommendation(
            status="empty",
            message="Type a question first, for example: *eco-friendly dye for red cotton*.",
        )

    parsed = parse_query(text)
    if not parsed.on_topic:
        return Recommendation(status="off_topic", message=OFF_TOPIC_MESSAGE, parsed=parsed)

    notes: list[str] = []

    # --- fibers and colors the dataset does not contain --------------------------------
    if parsed.unsupported_fibers:
        names = ", ".join(parsed.unsupported_fibers)
        if not parsed.fibers:
            return Recommendation(
                status="no_data",
                message=f"There is no data for **{names}** yet. Available fibers: {_available(data, 'Fiber')}.",
                parsed=parsed,
            )
        notes.append(f"No data for {names}; showing {', '.join(parsed.fibers)} only.")

    if parsed.unsupported_colors:
        names = ", ".join(parsed.unsupported_colors)
        if not parsed.colors:
            return Recommendation(
                status="no_data",
                message=f"There is no data for the color **{names}** yet. Available colors: {_available(data, 'Color')}.",
                parsed=parsed,
            )
        notes.append(f"No data for {names}; showing {', '.join(parsed.colors)} only.")

    # --- hard filters (fibers are never dropped) ---------------------------------------
    subset = data
    if parsed.fibers:
        subset = subset[_isin(subset, "Fiber", parsed.fibers)]

    hard: list[tuple[str, str, list[str]]] = []
    if parsed.method:
        hard.append(("dye method", "Dye Method", [parsed.method]))
    if parsed.shade:
        hard.append(("shade", "ShadeLevel", [parsed.shade]))
    if parsed.colors:
        hard.append(("color", "Color", parsed.colors))
    if parsed.dye_types:
        hard.append(("dye class", "DyeType", parsed.dye_types))

    def apply_hard(active: list[tuple[str, str, list[str]]]) -> pd.DataFrame:
        out = subset
        for _label, column, values in active:
            out = out[_isin(out, column, values)]
        return out

    filtered = apply_hard(hard)
    # Nothing matched: ignore the least important filters one by one and say so.
    dropped: list[str] = []
    active = list(hard)
    while filtered.empty and active:
        label, column, values = active.pop(0)
        filtered = apply_hard(active)
        dropped.append(
            f"{label} ({', '.join(values)}; available: {_available(subset, column)})"
        )
    if dropped:
        notes.append(
            "No recipe matches all your criteria, so these were ignored: "
            + "; ".join(dropped)
            + "."
        )

    # --- soft preferences -------------------------------------------------------------
    soft: list[tuple[str, Any]] = []
    if parsed.salt_free:
        soft.append(("salt-free", lambda d: d["NaCl Required"] == 0))
    if parsed.epa_only:
        soft.append(("EPA compliant", lambda d: d["EPA"].str.lower() == "yes"))
    if parsed.low_temp:
        soft.append((f"low temperature (<= {LOW_TEMPERATURE_MAX_C} °C)", lambda d: d["Temperature"] <= LOW_TEMPERATURE_MAX_C))

    active_soft = list(soft)
    candidate = filtered
    while active_soft:
        trial = candidate
        for _label, fn in active_soft:
            trial = trial[fn(trial)]
        if not trial.empty:
            candidate = trial
            break
        label, _fn = active_soft.pop()
        notes.append(f"No matching recipe is {label}, so that preference was ignored.")
    else:
        candidate = filtered

    if candidate.empty:  # defensive: cannot happen once fibers match, but never crash
        return Recommendation(
            status="no_data",
            message="No recipe in the dataset matches that request.",
            parsed=parsed,
            notes=notes,
        )

    # --- rank and pick ----------------------------------------------------------------
    ranked = _rank(candidate)
    key_cols = ["DyeType"] if candidate["Fiber"].nunique() == 1 else ["Fiber", "DyeType"]
    top = _pick_diverse(ranked, top_n, key_cols)

    options: list[dict[str, Any]] = []
    for position, (idx, row) in enumerate(top.iterrows(), start=1):
        item = row.to_dict()
        item["rank"] = position
        item["row_id"] = int(idx)
        options.append(item)

    return Recommendation(
        status="ok",
        options=options,
        notes=notes,
        parsed=parsed,
        matches=len(candidate),
    )
