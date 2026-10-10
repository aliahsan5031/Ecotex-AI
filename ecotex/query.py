"""Turn a free-text question into structured filters.

Everything here is rule based, so it is fast, free and predictable. Words are matched
with word boundaries, so "red" does not fire on "required" and "pet" not on "carpet".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def _rx(words: list[str]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(words) + r")\b", re.IGNORECASE)


# --- fibers -----------------------------------------------------------------------
FIBER_PATTERNS: dict[str, re.Pattern[str]] = {
    "Cotton": _rx(["cotton"]),
    "Polyester": _rx(["polyester", "pet", "poly"]),
    "Viscose": _rx(["viscose", "rayon"]),
    "Linen": _rx(["linen", "flax"]),
}
BLEND_PATTERN = _rx(
    [
        "blends?",
        "blended",
        r"mixed[- ]fabrics?",
        r"poly(?:ester)?[-/ ]?cotton",
        r"cotton[-/ ]?poly(?:ester)?",
    ]
)
# Fibers people ask about that the dataset does not cover.
UNSUPPORTED_FIBERS = _rx(
    [
        "wool",
        "silk",
        "nylon",
        "polyamide",
        "acrylic",
        "hemp",
        "jute",
        "bamboo",
        "modal",
        "lyocell",
        "tencel",
        "cashmere",
        "spandex",
        "elastane",
        "lycra",
    ]
)

# --- colors -----------------------------------------------------------------------
COLOR_PATTERNS: dict[str, re.Pattern[str]] = {
    c: _rx([c.lower()]) for c in ["Black", "Blue", "Green", "Navy", "Orange", "Red", "White", "Yellow"]
}
UNSUPPORTED_COLORS = _rx(
    [
        "purple",
        "violet",
        "pink",
        "grey",
        "gray",
        "brown",
        "maroon",
        "beige",
        "cream",
        "cyan",
        "magenta",
        "turquoise",
        "teal",
        "lavender",
        "gold",
        "silver",
        "olive",
        "burgundy",
        "khaki",
        "indigo",
        "mint",
        "coral",
        "lilac",
    ]
)

# --- other attributes ---------------------------------------------------------------
DYE_PATTERNS: dict[str, re.Pattern[str]] = {
    "Reactive": _rx(["reactive"]),
    "Disperse": _rx(["disperse"]),
    "Vat": _rx(["vat"]),
    "Sulfur": _rx(["sulfur", "sulphur"]),
    "Direct": _rx(["direct"]),
    "Acid": _rx(["acid"]),
    "Cationic": _rx(["cationic", "basic"]),
}
SHADE_PATTERNS: dict[str, re.Pattern[str]] = {
    "Light": _rx(["light", "pale", "pastel"]),
    "Medium": _rx(["medium", "mid"]),
    "Dark": _rx(["dark", "deep", "heavy"]),
}
SEMI_CONTINUOUS = re.compile(r"\bsemi[- ]?continuous\b", re.IGNORECASE)
CONTINUOUS = _rx(["continuous"])
BATCH = _rx(["batch", "exhaust", "exhaustion"])

LOW_TEMP = re.compile(
    r"\b(?:low|lower|cold|reduced)[- ]?(?:temp|temperature)\b|\bcold[- ]dye\w*|\benergy[- ]sav\w*",
    re.IGNORECASE,
)
SALT_FREE = re.compile(
    r"\b(?:salt[- ]?free|no[- ]salt|without[- ]salt|zero[- ]salt|no[- ]nacl|nacl[- ]free)\b",
    re.IGNORECASE,
)
EPA_PATTERN = _rx(["epa", "compliant"])

# --- domain guard -------------------------------------------------------------------
CORE_TEXTILE_TERMS = _rx(
    [
        r"dy(?:e|es|ed|eing|estuffs?)",
        "fabrics?",
        r"fib(?:er|re)s?",
        "textiles?",
        "yarns?",
        "garments?",
        "liquor",
        "mordants?",
        "scouring",
        r"bleach\w*",
        "effluent",
        "wastewater",
        "shade",
        "nacl",
        "tenacity",
        "auxiliar(?:y|ies)",
    ]
)

LOW_TEMPERATURE_MAX_C = 60


@dataclass
class ParsedQuery:
    raw: str
    on_topic: bool = False
    fibers: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    dye_types: list[str] = field(default_factory=list)
    shade: str | None = None
    method: str | None = None
    low_temp: bool = False
    salt_free: bool = False
    epa_only: bool = False
    unsupported_fibers: list[str] = field(default_factory=list)
    unsupported_colors: list[str] = field(default_factory=list)

    def describe(self) -> str:
        """Short human-readable summary of what was understood."""
        parts: list[str] = []
        if self.fibers:
            parts.append("Fiber: " + ", ".join(self.fibers))
        if self.colors:
            parts.append("Color: " + ", ".join(self.colors))
        if self.dye_types:
            parts.append("Dye class: " + ", ".join(self.dye_types))
        if self.shade:
            parts.append(f"Shade: {self.shade}")
        if self.method:
            parts.append(f"Method: {self.method}")
        if self.low_temp:
            parts.append(f"Low temperature (<= {LOW_TEMPERATURE_MAX_C} °C)")
        if self.salt_free:
            parts.append("Salt-free")
        if self.epa_only:
            parts.append("EPA compliant")
        return " · ".join(parts) if parts else "No specific filters detected"


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def parse_query(query: str) -> ParsedQuery:
    """Extract fiber, color, shade, method and preferences from ``query``."""
    text = (query or "").strip()
    parsed = ParsedQuery(raw=text)
    if not text:
        return parsed

    # "navy blue" is one color, not navy + blue.
    work = re.sub(r"\bnavy[- ]blue\b", "navy", text, flags=re.IGNORECASE)

    # Fibers
    if BLEND_PATTERN.search(work):
        parsed.fibers = ["Blended"]
    else:
        parsed.fibers = [name for name, rx in FIBER_PATTERNS.items() if rx.search(work)]
    parsed.unsupported_fibers = _unique([m.group(0).capitalize() for m in UNSUPPORTED_FIBERS.finditer(work)])

    # Colors
    parsed.colors = [name for name, rx in COLOR_PATTERNS.items() if rx.search(work)]
    parsed.unsupported_colors = _unique([m.group(0).capitalize() for m in UNSUPPORTED_COLORS.finditer(work)])

    # Dye classes, shade, method
    parsed.dye_types = [name for name, rx in DYE_PATTERNS.items() if rx.search(work)]
    for name, rx in SHADE_PATTERNS.items():
        if rx.search(work):
            parsed.shade = name
            break
    if SEMI_CONTINUOUS.search(work):
        parsed.method = "Semi-continuous"
    elif CONTINUOUS.search(work):
        parsed.method = "Continuous"
    elif BATCH.search(work):
        parsed.method = "Batch"

    # Preferences
    parsed.low_temp = bool(LOW_TEMP.search(work))
    parsed.salt_free = bool(SALT_FREE.search(work))
    parsed.epa_only = bool(EPA_PATTERN.search(work))

    # Domain guard: a textile term, any fiber, or a dye class together with a color/shade/method.
    has_fiber = bool(parsed.fibers or parsed.unsupported_fibers)
    has_core_term = bool(CORE_TEXTILE_TERMS.search(work))
    dye_class_in_context = bool(parsed.dye_types and (parsed.colors or parsed.shade or parsed.method))
    parsed.on_topic = has_fiber or has_core_term or dye_class_in_context
    return parsed
