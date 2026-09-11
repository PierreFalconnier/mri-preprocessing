import os
from pathlib import Path

import nibabel as nib
import numpy as np
from tqdm import tqdm


def process_file(src_path: Path, dst_base: Path, root_src: Path):
    """
    Load full .nii.gz volume, decompress it, and save as .npy

    Input:
        sub-XXX_ses-YYY_space-MNI_desc-brain.nii.gz

    Output:
        sub-XXX_ses-YYY_space-MNI_desc-brain.npy
    """
    rel_path = src_path.relative_to(root_src)

    dst_dir = dst_base / rel_path.parent
    dst_dir.mkdir(parents=True, exist_ok=True)

    # Load full decompressed volume
    img = nib.load(str(src_path))
    volume = img.get_fdata(dtype=np.float32)

    base_name = src_path.name.replace(".nii.gz", "")

    np.save(dst_dir / f"{base_name}.npy", volume)


def convert_bids_dataset(src_dir, dst_dir):
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)

    files_to_process = []

    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith("brain.nii.gz"):
                files_to_process.append(Path(root) / f)

    for full_path in tqdm(files_to_process, desc="Converting files", unit="file"):
        process_file(full_path, dst_dir, src_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert BIDS brain.nii.gz files to decompressed 3D .npy volumes"
    )
    parser.add_argument("src", type=str, help="Source BIDS dataset path")
    parser.add_argument("dst", type=str, help="Destination dataset path")

    args = parser.parse_args()

    convert_bids_dataset(args.src, args.dst)
