"""Generic DICOM -> BIDS conversion driver.

Walks the flattened raw tree via the dataset adapter, matches each image to
its row in the merged metadata CSV, asks the adapter for a BIDS filename,
and runs dcm2niix. All dataset-specific knowledge lives in the adapter
(`mri_prep.datasets.*`); this module only orchestrates.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from mri_prep.config import DatasetConfig
from mri_prep.datasets import get_adapter


def convert_to_bids(
    config: DatasetConfig,
    image_id_col: str = "Image ID",
    subject_col: str = "PATNO",
    session_col: str = "EVENT_ID",
    modality_col: str = "BIDS_Modality",
) -> None:
    adapter = get_adapter(config.adapter)
    raw_root = config.paths.flattened_root or config.paths.raw_dicom_root
    if raw_root is None:
        raise ValueError("Dataset config needs paths.flattened_root or paths.raw_dicom_root")
    bids_root = Path(config.paths.bids_root)
    bids_root.mkdir(parents=True, exist_ok=True)

    merged_csv = config.extra.get("merged_csv")
    if not merged_csv:
        raise ValueError("Dataset config needs extra.merged_csv (output of `mri-prep tabular merge`)")
    df = pd.read_csv(merged_csv, dtype=str)
    df[image_id_col] = df[image_id_col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)

    n_matched, n_unmatched, n_failed = 0, 0, 0
    for image_id, image_dir in tqdm(list(adapter.iter_source_images(Path(raw_root)))):
        row = df[df[image_id_col] == image_id]
        if len(row) == 0:
            n_unmatched += 1
            continue
        row = row.iloc[0]

        bids_name = adapter.build_bids_name(row)
        if bids_name is None:
            continue

        sub = f"sub-{row[subject_col]}"
        ses = f"ses-{row[session_col]}"
        mod = row[modality_col]
        dest_dir = bids_root / sub / ses / mod
        dest_dir.mkdir(parents=True, exist_ok=True)

        cmd = ["dcm2niix", "-z", "y", "-f", bids_name, "-o", str(dest_dir), str(image_dir)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            n_matched += 1
        except subprocess.CalledProcessError as e:
            n_failed += 1
            print(f"dcm2niix failed for image {image_id}: {e.stderr}")

    print(f"Converted: {n_matched}, unmatched (no CSV row): {n_unmatched}, dcm2niix failures: {n_failed}")
