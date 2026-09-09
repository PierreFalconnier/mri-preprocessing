"""Build a flat index (one row per image/derivative file) of a BIDS-shaped
directory tree.

This is what lets the tabular layer answer questions like "which subjects
have both a T1w and a NM scan at every visit" without re-walking the
filesystem every time -- index once, then filter the DataFrame.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

BIDS_ENTITY_RE = re.compile(r"sub-(?P<subject>[^_/]+)_ses-(?P<session>[^_/]+)")
SUFFIX_RE = re.compile(r"_(?P<suffix>[A-Za-z0-9]+)\.nii(\.gz)?$")
RUN_RE = re.compile(r"run-(?P<run>\d+)")
ACQ_RE = re.compile(r"acq-(?P<acq>[^_]+)")


def index_bids_tree(root: Path, pattern: str = "*.nii.gz") -> pd.DataFrame:
    """Scan `root` for files matching `pattern` and parse BIDS entities out
    of their filenames. Works on a raw BIDS dataset or a turboprep output
    tree (sub-*/ses-*/anat/*_brain.nii.gz etc.) alike.
    """
    root = Path(root)
    rows = []
    for path in root.rglob(pattern):
        name = path.name
        m = BIDS_ENTITY_RE.search(name)
        if not m:
            continue
        suffix_m = SUFFIX_RE.search(name)
        run_m = RUN_RE.search(name)
        acq_m = ACQ_RE.search(name)
        rows.append(
            {
                "subject": m.group("subject"),
                "session": m.group("session"),
                "suffix": suffix_m.group("suffix") if suffix_m else None,
                "run": int(run_m.group("run")) if run_m else None,
                "acq": acq_m.group("acq") if acq_m else None,
                "path": str(path),
                "filename": name,
            }
        )
    return pd.DataFrame(rows)


def modality_availability(index: pd.DataFrame) -> pd.DataFrame:
    """Pivot the index into one row per (subject, session) with a boolean
    column per suffix found (e.g. T1w, dwi, bold) -- the quickest way to
    answer "who has modality X at visit Y"."""
    if index.empty:
        return index
    pivot = (
        index.assign(present=True)
        .pivot_table(
            index=["subject", "session"],
            columns="suffix",
            values="present",
            aggfunc="any",
            fill_value=False,
        )
        .reset_index()
    )
    return pivot
