"""Export segmentation region fractions, with one row per subject/session.

Total brain volume is all nonzero mask voxels, including CSF and ventricles.
Because every voxel in a mask has the same volume, voxel-count ratios equal
physical-volume ratios. Background (label 0) is excluded from the CSV.
The 15 requested regions combine left and right labels where applicable.
CSF includes only label 24; ventricles are reported separately.

Usage:
    python preprocessing/relative_region_volumes.py /path/to/dataset \
        --output /path/to/relative_region_volumes.csv
"""

import argparse
import csv
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

# SynthSeg/FreeSurfer labels from quality_control/labels table.txt.
# Background (0) is omitted because it is excluded from brain volume.
REGION_LABELS: dict[int, str] = {
    2: "left cerebral white matter",
    3: "left cerebral cortex",
    4: "left lateral ventricle",
    5: "left inferior lateral ventricle",
    7: "left cerebellum white matter",
    8: "left cerebellum cortex",
    10: "left thalamus",
    11: "left caudate",
    12: "left putamen",
    13: "left pallidum",
    14: "3rd ventricle",
    15: "4th ventricle",
    16: "brain-stem",
    17: "left hippocampus",
    18: "left amygdala",
    26: "left accumbens area",
    24: "CSF",
    28: "left ventral DC",
    41: "right cerebral white matter",
    42: "right cerebral cortex",
    43: "right lateral ventricle",
    44: "right inferior lateral ventricle",
    46: "right cerebellum white matter",
    47: "right cerebellum cortex",
    49: "right thalamus",
    50: "right caudate",
    51: "right putamen",
    52: "right pallidum",
    53: "right hippocampus",
    54: "right amygdala",
    58: "right accumbens area",
    60: "right ventral DC",
}


REGION_GROUPS: dict[str, tuple[int, ...]] = {
    "hippocampus": (17, 53),
    "amygdala": (18, 54),
    "lateral ventricles": (4, 43),
    "cerebral cortex": (3, 42),
    "inferior lateral ventricle": (5, 44),
    "cerebellum cortex": (8, 47),
    "thalamus": (10, 49),
    "caudate": (11, 50),
    "putamen": (12, 51),
    "pallidum": (13, 52),
    "accumbens": (26, 58),
    "ventral DC": (28, 60),
    "3rd ventricle": (14,),
    "4th ventricle": (15,),
    "csf": (24,),
}


def relative_volumes(
    mask_path: Path, regions: dict[str, tuple[int, ...]]
) -> dict[str, float]:
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
    unknown = sorted(set(voxel_counts) - {0} - set(REGION_LABELS))
    if unknown:
        print(
            f"WARNING: {mask_path}: unmapped labels {unknown}; "
            "included in total volume but have no CSV columns",
            file=sys.stderr,
        )
    return {
        name: sum(voxel_counts.get(value, 0) for value in values) / total
        for name, values in regions.items()
    }


def export_volumes(
    dataset: Path, output: Path, regions: dict[str, tuple[int, ...]]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    processed = 0
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["subject", "session", *regions]
        )
        writer.writeheader()
        for subject in sorted(dataset.glob("sub-*")):
            if not subject.is_dir():
                continue
            for session in sorted(subject.glob("ses-*")):
                if not session.is_dir():
                    continue
                row = {
                    "subject": subject.name.replace("sub-", ""),
                    "session": session.name.replace("ses-", ""),
                }
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
                        row.update(relative_volumes(masks[0], regions))
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
    args = parser.parse_args()
    if not args.dataset.is_dir():
        parser.error(f"Dataset directory does not exist: {args.dataset}")
    export_volumes(
        args.dataset,
        args.output or args.dataset / "relative_region_volumes.csv",
        REGION_GROUPS,
    )


if __name__ == "__main__":
    main()
