import os
from pathlib import Path

import nibabel as nib
import numpy as np


def get_middle_slices(volume):
    """
    volume shape assumed: (X, Y, Z)
    Returns raw (no normalization) axial, coronal, sagittal slices
    """
    x, y, z = volume.shape

    axial = volume[:, :, z // 2]
    coronal = volume[:, y // 2, :]
    sagittal = volume[x // 2, :, :]

    return axial, coronal, sagittal


def process_file(src_path: Path, dst_base: Path, root_src: Path):
    rel_path = src_path.relative_to(root_src)

    dst_dir = dst_base / rel_path.parent
    dst_dir.mkdir(parents=True, exist_ok=True)

    img = nib.load(str(src_path))

    # Get shape WITHOUT loading data
    x, y, z = img.shape

    proxy = img.dataobj  # ArrayProxy

    # only load required slices
    axial = np.asanyarray(proxy[:, :, z // 2])
    coronal = np.asanyarray(proxy[:, y // 2, :])
    sagittal = np.asanyarray(proxy[x // 2, :, :])

    base_name = src_path.name.replace("brain.nii.gz", "")

    np.save(dst_dir / f"{base_name}axial.npy", axial)
    np.save(dst_dir / f"{base_name}coronal.npy", coronal)
    np.save(dst_dir / f"{base_name}sagittal.npy", sagittal)


def convert_bids_dataset(src_dir, dst_dir):
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)

    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith("brain.nii.gz"):
                full_path = Path(root) / f
                process_file(full_path, dst_dir, src_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert BIDS T1w brain.nii.gz to middle-slice .npy arrays (raw values)"
    )
    parser.add_argument("src", type=str, help="Source BIDS dataset path")
    parser.add_argument("dst", type=str, help="Destination dataset path")

    args = parser.parse_args()

    convert_bids_dataset(args.src, args.dst)
