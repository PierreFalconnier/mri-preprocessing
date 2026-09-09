"""Generic loading of a dataset's raw CSV exports into DataFrames."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_dataset_csvs(base_dir: Path, remove_date_suffix: bool = True) -> dict[str, pd.DataFrame]:
    """Load every CSV under `base_dir` into {clean_name: DataFrame}.

    Column names are upper-cased/stripped for consistent joins. When
    `remove_date_suffix` is set, a trailing "_<date>" in the filename (as
    produced by ida.loni study data downloads, e.g.
    "Demographics_18Feb2026.csv") is stripped from the table name.
    """
    base_dir = Path(base_dir)
    data: dict[str, pd.DataFrame] = {}
    for csv_path in sorted(base_dir.rglob("*.csv")):
        df = pd.read_csv(csv_path, low_memory=False)
        df.columns = df.columns.str.strip().str.upper()

        stem = csv_path.stem
        name = stem.rsplit("_", 1)[0] if remove_date_suffix else stem
        data[name] = df
    return data
