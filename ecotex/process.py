"""Process outline and explanation text for a recipe.

The outline is built only from dataset values, so nothing is invented. If a Groq API key
is configured, the explanation sentence is written by the model instead; if the call
fails for any reason the built-in explanation is used.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any

from .data import SCORE_PARTS

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def fmt(value: Any) -> str:
    """Format numbers without a trailing .0 (90.0 -> 90, 1.30 -> 1.3)."""
    if isinstance(value, bool) or value is None:
        return str(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number != number:  # NaN
        return "-"
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def process_steps(row: dict[str, Any]) -> list[str]:
    """Numbered process outline using only values stored for this recipe."""
    fiber = str(row["Fiber"]).lower()
    dye = str(row["DyeType"]).lower()
    nacl = float(row["NaCl Required"])

    steps = [
        f"Prepare the dye bath at a liquor ratio of {row['LiquorRatio']}.",
        (
            f"Add the {dye} dye for {fiber} at a dye concentration of {fmt(row['Dye Concentration'])} "
            f"to reach a {str(row['Color']).lower()} {str(row['ShadeLevel']).lower()} shade "
            f"(shade {fmt(row['Shade %'])}%)."
        ),
        f"Adjust the bath to pH {fmt(row['pH'])}.",
        (
            "No salt (NaCl) addition is required."
            if nacl == 0
            else f"Add NaCl at {fmt(nacl)}."
        ),
        (
            f"Heat the bath to {fmt(row['Temperature'])} °C and dye by the "
            f"{str(row['Dye Method']).lower()} method until the target shade is reached."
        ),
        f"Rinse and wash off with your standard after-treatment for {dye} dyes.",
        (
            f"Check the effluent against the recorded dye residue ({fmt(row['Dye Residues'])}) "
            f"and the dye tenacity rating ({row['Dye Tenacity']})."
        ),
    ]
    return steps


def score_parts(row: dict[str, Any]) -> list[tuple[str, float, float]]:
    """(label, points, maximum) for each part of the Eco Score."""
    return [(label, float(row[col]), float(maximum)) for col, label, maximum in SCORE_PARTS]


def builtin_explanation(row: dict[str, Any]) -> str:
    """Strongest and weakest part of the score, in plain words."""
    parts = score_parts(row)
    best = max(parts, key=lambda p: p[1] / p[2])
    worst = min(parts, key=lambda p: p[1] / p[2])
    text = (
        f"Eco Score {fmt(row['Eco Score'])}/100 ({row['Eco Rating']}). "
        f"Strongest factor: {best[0]} ({fmt(best[1])}/{fmt(best[2])}). "
    )
    if worst[1] / worst[2] < 1:
        text += f"Weakest factor: {worst[0]} ({fmt(worst[1])}/{fmt(worst[2])})."
    else:
        text += "It scores full points on every factor."
    return text


# --- optional Groq explanation --------------------------------------------------------
def llm_enabled() -> bool:
    return bool(os.getenv("GROQ_API_KEY")) and os.getenv("ECOTEX_USE_LLM", "1").strip() != "0"


@lru_cache(maxsize=256)
def _llm_call(facts_json: str) -> str:
    """Cached model call. Raises on failure so failures are never cached."""
    from groq import Groq  # imported lazily so the app runs without the package/key

    client = Groq(timeout=20.0, max_retries=1)
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", DEFAULT_MODEL),
        temperature=0,
        max_tokens=160,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a textile dyeing sustainability advisor. In two short sentences, explain "
                    "the environmental strengths and weaknesses of the dye recipe described by the JSON. "
                    "Use only the facts and numbers in the JSON. Do not invent values, chemicals or steps. "
                    "Plain text, no markdown."
                ),
            },
            {"role": "user", "content": facts_json},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("empty model response")
    return text.replace("*", "").replace("#", "")


def explain(row: dict[str, Any]) -> tuple[str, bool]:
    """Return (explanation, written_by_model)."""
    fallback = builtin_explanation(row)
    if not llm_enabled():
        return fallback, False
    facts = {
        "fiber": row["Fiber"],
        "dye_class": row["DyeType"],
        "color": row["Color"],
        "eco_score": row["Eco Score"],
        "eco_rating": row["Eco Rating"],
        "epa_compliant": row["EPA"],
        "temperature_c": fmt(row["Temperature"]),
        "nacl_required": fmt(row["NaCl Required"]),
        "dye_residues": fmt(row["Dye Residues"]),
        "dye_tenacity": row["Dye Tenacity"],
        "score_breakdown": {label: f"{fmt(pts)}/{fmt(mx)}" for label, pts, mx in score_parts(row)},
    }
    try:
        return _llm_call(json.dumps(facts, sort_keys=True)), True
    except Exception as exc:  # network, quota, bad key, ... never break the page
        logger.warning("LLM explanation failed, using built-in text: %s", exc)
        return fallback, False


def explain_many(rows: list[dict[str, Any]]) -> list[tuple[str, bool]]:
    """Explain several options; model calls run in parallel."""
    if len(rows) > 1 and llm_enabled():
        with ThreadPoolExecutor(max_workers=min(len(rows), 4)) as pool:
            return list(pool.map(explain, rows))
    return [explain(r) for r in rows]
