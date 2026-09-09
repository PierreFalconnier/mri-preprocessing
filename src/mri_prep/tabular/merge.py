"""Merge a dict of {table_name: DataFrame} into one wide table, keyed on
subject id (+ visit id when the table is visit-level).

Generalized from `csv_exploration/PPMI_explo/ppmi_utils.py`. Works for any
dataset whose tables share a subject-id column and, for visit-level tables,
a visit-id column (PPMI: PATNO/EVENT_ID).
"""

from __future__ import annotations

import pandas as pd


def build_visit_backbone(
    tables: dict[str, pd.DataFrame], subject_col: str, visit_col: str
) -> pd.DataFrame:
    visit_tables = [
        (name, df.copy())
        for name, df in tables.items()
        if {subject_col, visit_col}.issubset(df.columns)
    ]
    if not visit_tables:
        raise ValueError(f"No visit-level tables found (need columns {subject_col}, {visit_col}).")

    _, backbone = visit_tables[0]
    for name, df in visit_tables[1:]:
        backbone = backbone.merge(
            df, on=[subject_col, visit_col], how="outer", suffixes=("", f"_{name}")
        )
    return backbone


def add_subject_level_tables(
    backbone: pd.DataFrame, tables: dict[str, pd.DataFrame], subject_col: str, visit_col: str
) -> pd.DataFrame:
    for name, df in tables.items():
        if subject_col in df.columns and visit_col not in df.columns:
            backbone = backbone.merge(df, on=subject_col, how="left", suffixes=("", f"_{name}"))
    return backbone


def merge_dataset_tables(
    tables: dict[str, pd.DataFrame], subject_col: str = "PATNO", visit_col: str = "EVENT_ID"
) -> pd.DataFrame:
    """Merge visit-level tables on (subject, visit), then left-join
    subject-level (visit-independent) tables on subject id."""
    backbone = build_visit_backbone(tables, subject_col, visit_col)
    return add_subject_level_tables(backbone, tables, subject_col, visit_col)
