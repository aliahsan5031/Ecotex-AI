"""Dataset loading and validation."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ecotex_dataset.csv"

TEXT_COLUMNS = [
    "Fiber",
    "DyeType",
    "Color",
    "EPA",
    "ShadeLevel",
    "Dye Method",
    "LiquorRatio",
    "Dye Tenacity",
    "Eco Rating",
]

NUMERIC_COLUMNS = [
    "Temperature",
    "Dye Concentration",
    "Shade %",
    "Dye Residues",
    "NaCl Required",
    "pH",
    "Eco Score",
]

# (CSV column, label shown to the user, maximum points)
SCORE_PARTS: list[tuple[str, str, float]] = [
    ("Score EPA(20)", "EPA compliance", 20),
    ("Score Tenacity(20)", "Dye tenacity", 20),
    ("Score_Residues(20)", "Low dye residues", 20),
    ("Score_NaCl(15)", "Low salt (NaCl)", 15),
    ("Score Temperature(15)", "Low temperature", 15),
    ("Score DyeType(10)", "Dye class", 10),
]

REQUIRED_COLUMNS = TEXT_COLUMNS + NUMERIC_COLUMNS + [part[0] for part in SCORE_PARTS]


class DatasetError(ValueError):
    """Raised when the dataset file is missing or malformed."""


def load_dataset(path: str | os.PathLike | None = None) -> pd.DataFrame:
    """Read and validate the recipe dataset.

    The path can be given explicitly or through the ``ECOTEX_DATA`` environment variable.
    """
    csv_path = Path(path or os.getenv("ECOTEX_DATA") or DEFAULT_DATA_PATH)
    if not csv_path.is_file():
        raise DatasetError(f"Dataset not found: {csv_path}")

    df = pd.read_csv(csv_path)
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DatasetError(f"Dataset is missing columns: {', '.join(missing)}")

    for col in TEXT_COLUMNS:
        df[col] = df[col].astype(str).str.strip()
    for col in NUMERIC_COLUMNS + [part[0] for part in SCORE_PARTS]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Fiber", "DyeType", "Color", "Eco Score"]).reset_index(drop=True)
    if df.empty:
        raise DatasetError("Dataset contains no usable rows.")
    return df


@lru_cache(maxsize=1)
def get_dataset() -> pd.DataFrame:
    """Cached copy of the default dataset (do not mutate it)."""
    return load_dataset()
