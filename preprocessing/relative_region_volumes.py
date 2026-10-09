"""Export segmentation region fractions, with one row per subject/session.

Total brain volume is all nonzero mask voxels, including CSF and ventricles.
Because every voxel in a mask has the same volume, voxel-count ratios equal
physical-volume ratios. Background (label 0) is excluded from the CSV.

Usage:
    python preprocessing/relative_region_volumes.py /path/to/dataset \
        --output /path/to/relative_region_volumes.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

DEFAULT_LABELS = (
    Path(__file__).resolve().parents[1] / "quality_control/labels table.txt"
)


def read_labels(path: Path) -> dict[int, str]:
    """Read numeric label rows, ignoring the table's introductory text."""
    labels = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*(\d+)\s+(.+?)\s*$", line)
        if match:
            value, name = int(match[1]), match[2]
            if value in labels:
                raise ValueError(f"Duplicate label {value} in {path}")
            if value != 0:
                labels[value] = name
    if not labels:
        raise ValueError(f"No region labels found in {path}")
    if len(set(labels.values())) != len(labels):
        raise ValueError(f"Duplicate region names in {path}")
    if {"subject_id", "session_id"} & set(labels.values()):
        raise ValueError(f"Region names conflict with CSV identifier columns in {path}")
    return labels


def relative_volumes(mask_path: Path, labels: dict[int, str]) -> dict[str, float]:
    image = nib.load(mask_path)
    if len(image.shape) != 3:
        raise ValueError(f"Expected a 3D segmentation, got shape {image.shape}")
    data = np.asanyarray(image.dataobj)
    if not np.all(np.isfinite(data)):
        raise ValueError("Segmentation contains non-finite values")
    if np.any(data < 0) or np.any(data != np.floor(data)):
        raise ValueError("Segmentation must contain nonnegative integer labels")
    values, counts = np.unique(data, return_counts=True)
    voxel_counts = dict(zip(values.tolist(), counts.tolist()))
    total = sum(count for value, count in voxel_counts.items() if value != 0)
    if total == 0:
        raise ValueError("Segmentation contains only background")
    unknown = sorted(set(voxel_counts) - {0} - set(labels))
    if unknown:
        print(
            f"WARNING: {mask_path}: unmapped labels {unknown}; "
            "included in total volume but have no CSV columns",
            file=sys.stderr,
        )
    return {name: voxel_counts.get(value, 0) / total for value, name in labels.items()}


def export_volumes(dataset: Path, output: Path, labels: dict[int, str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    processed = 0
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["subject_id", "session_id", *labels.values()]
        )
        writer.writeheader()
        for subject in sorted(dataset.glob("sub-*")):
            if not subject.is_dir():
                continue
            for session in sorted(subject.glob("ses-*")):
                if not session.is_dir():
                    continue
                row = {"subject_id": subject.name, "session_id": session.name}
                masks = sorted(
                    path
                    for path in (session / "anat").rglob("*T1w_segm.nii.gz")
                    if path.is_file()
                )
                if not masks:
                    print(
                        f"WARNING: {session}: no segmentation; writing empty values",
                        file=sys.stderr,
                    )
                else:
                    if len(masks) > 1:
                        print(
                            f"WARNING: {session}: found {len(masks)} masks; using {masks[0]}",
                            file=sys.stderr,
                        )
                    try:
                        row.update(relative_volumes(masks[0], labels))
                        processed += 1
                    except (
                        OSError,
                        ValueError,
                        EOFError,
                        nib.filebasedimages.ImageFileError,
                    ) as error:
                        print(
                            f"WARNING: {masks[0]}: {error}; writing empty values",
                            file=sys.stderr,
                        )
                writer.writerow(row)
                rows += 1
    print(f"Saved {rows} sessions ({processed} masks processed) to {output}")
    if rows == 0:
        print("WARNING: no sub-*/ses-* directories found", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "dataset", type=Path, help="Dataset containing sub-*/ses-*/anat directories"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV (default: DATASET/relative_region_volumes.csv)",
    )
    parser.add_argument(
        "--labels", type=Path, default=DEFAULT_LABELS, help="Label table path"
    )
    args = parser.parse_args()
    if not args.dataset.is_dir():
        parser.error(f"Dataset directory does not exist: {args.dataset}")
    try:
        labels = read_labels(args.labels)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    export_volumes(
        args.dataset,
        args.output or args.dataset / "relative_region_volumes.csv",
        labels,
    )


if __name__ == "__main__":
    main()
