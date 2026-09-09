"""Flatten turboprep's per-run subdirectories into prefixed files sitting
directly in the anat/ folder, e.g.

    sub-X/ses-Y/anat/sub-X_ses-Y_T1w/brain.nii.gz
    -> sub-X/ses-Y/anat/sub-X_ses-Y_T1w_brain.nii.gz

via symlinks, so downstream code can glob for files by suffix without
knowing about the per-run directory layout.

Ported from `bash_scripts/reorganize_preprocessed_dataset.py`.
"""

from __future__ import annotations

import os
from pathlib import Path


def reorganize_preprocessed(source_root: str | Path, destination_root: str | Path) -> None:
    source_root, destination_root = str(source_root), str(destination_root)

    for dirpath, dirnames, _ in os.walk(source_root):
        if os.path.basename(dirpath) != "anat":
            continue

        for subdir in dirnames:
            subdir_path = os.path.join(dirpath, subdir)
            if not os.path.isdir(subdir_path):
                continue

            prefix = subdir  # e.g. sub-3055_ses-..._T1w

            rel_path = os.path.relpath(dirpath, source_root)
            dest_anat = os.path.join(destination_root, rel_path)
            os.makedirs(dest_anat, exist_ok=True)

            for fname in os.listdir(subdir_path):
                src = os.path.join(subdir_path, fname)
                if not os.path.isfile(src):
                    continue

                dst = os.path.join(dest_anat, f"{prefix}_{fname}")
                if os.path.exists(dst):
                    print(f"Skipping (exists): {dst}")
                    continue

                os.symlink(src, dst)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    reorganize_preprocessed(args.source, args.destination)
