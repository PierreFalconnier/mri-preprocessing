"""ADNI dataset adapter (stub).

ADNI's raw layout and CSV schema differ from PPMI's, so this adapter isn't a
full port yet -- fill in `build_bids_name` / `iter_source_images` following
the same pattern as `mri_prep.datasets.ppmi.PPMIAdapter` once you get to
ADNI BIDS conversion. `load_tabular` already works since ADNI's CSV exports
have the same PATNO/EVENT_ID-shaped tables as PPMI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd


class ADNIAdapter:
    def build_bids_name(self, row: pd.Series) -> str | None:
        raise NotImplementedError(
            "ADNI BIDS naming not ported yet -- see legacy/bash_scripts/adni_turbo_prep_to_bids.py "
            "for the reorganization logic used so far (groups by subject_id/image_date)."
        )

    def iter_source_images(self, raw_root: Path) -> Iterator[tuple[str, Path]]:
        raise NotImplementedError

    def load_tabular(self, csv_root: Path) -> dict[str, pd.DataFrame]:
        from mri_prep.tabular.io import load_dataset_csvs

        return load_dataset_csvs(csv_root)
