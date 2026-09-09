"""Cohort selection: join clinical/tabular data with imaging availability
and filter down to exactly the subjects/visits you need.

This is the main entry point for "give me exactly what I want out of the
data" -- e.g.:

    cohort = Cohort.from_dataset("ppmi")
    cohort = cohort.with_modality("T1w").with_min_visits(3).where(COHORT="Parkinson's Disease")
    cohort.subjects  # -> list of PATNOs
    cohort.table     # -> the filtered merged DataFrame
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from mri_prep.bids.index import index_bids_tree, modality_availability
from mri_prep.config import DatasetConfig, load_dataset_config
from mri_prep.datasets import get_adapter
from mri_prep.tabular.merge import merge_dataset_tables


@dataclass
class Cohort:
    table: pd.DataFrame
    subject_col: str = "PATNO"
    visit_col: str = "EVENT_ID"

    @classmethod
    def from_dataset(
        cls,
        name: str,
        subject_col: str = "PATNO",
        visit_col: str = "EVENT_ID",
        config: DatasetConfig | None = None,
    ) -> "Cohort":
        config = config or load_dataset_config(name)
        adapter = get_adapter(config.adapter)
        tables = adapter.load_tabular(config.paths.csv_root)
        merged = merge_dataset_tables(tables, subject_col=subject_col, visit_col=visit_col)
        return cls(table=merged, subject_col=subject_col, visit_col=visit_col)

    # -- filtering --------------------------------------------------

    def where(self, **equals) -> "Cohort":
        """Keep rows where every given column equals the given value."""
        df = self.table
        for col, value in equals.items():
            df = df[df[col] == value]
        return Cohort(df, self.subject_col, self.visit_col)

    def with_min_visits(self, n: int) -> "Cohort":
        counts = self.table.groupby(self.subject_col)[self.visit_col].nunique()
        keep = counts[counts >= n].index
        return Cohort(self.table[self.table[self.subject_col].isin(keep)], self.subject_col, self.visit_col)

    def with_modality(self, *suffixes: str, bids_root: Path | None = None) -> "Cohort":
        """Restrict to subjects that have every given modality suffix
        (e.g. 'T1w', 'dwi') available, according to a BIDS index built from
        `bids_root`. Requires the table to already carry a 'subject'
        column matching the BIDS subject label, or set `subject_col`
        accordingly before calling this."""
        if bids_root is None:
            raise ValueError("with_modality requires bids_root (path to the BIDS/processed tree)")
        index = index_bids_tree(Path(bids_root))
        avail = modality_availability(index)
        for suffix in suffixes:
            if suffix not in avail.columns:
                avail[suffix] = False
            avail = avail[avail[suffix]]
        keep_subjects = set(avail["subject"])
        df = self.table[self.table[self.subject_col].astype(str).isin(keep_subjects)]
        return Cohort(df, self.subject_col, self.visit_col)

    # -- accessors ----------------------------------------------------

    @property
    def subjects(self) -> list:
        return sorted(self.table[self.subject_col].dropna().unique().tolist())

    def __len__(self) -> int:
        return self.table[self.subject_col].nunique()

    def to_csv(self, path: str | Path) -> None:
        self.table.to_csv(path, index=False)
