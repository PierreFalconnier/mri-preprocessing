"""Protocol every dataset adapter must implement.

A dataset adapter is the *only* place that should know about a dataset's
idiosyncratic raw layout (folder naming, CSV columns, visit-code
vocabularies, ...). Everything downstream (preprocessing, QC, export,
tabular merge) is generic and works off BIDS paths + a plain DataFrame.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd


class DatasetAdapter(Protocol):
    """Interface used by `mri_prep.bids.convert` and `mri_prep.tabular`."""

    def build_bids_name(self, row: pd.Series) -> str | None:
        """Given one row of the dataset's merged metadata table, return the
        BIDS filename stem (without extension) for the corresponding image,
        or None if this row should be skipped."""
        ...

    def iter_source_images(self, raw_root: Path):
        """Yield (image_id, dicom_dir) pairs found under the flattened raw
        source tree, to be matched against the metadata table."""
        ...

    def load_tabular(self, csv_root: Path) -> dict[str, pd.DataFrame]:
        """Load the dataset's raw CSVs into {table_name: DataFrame}."""
        ...
