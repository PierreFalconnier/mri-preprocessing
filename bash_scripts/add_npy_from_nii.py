"""
Convert matching .nii.gz files to preprocessed .npy arrays using Yucca.

Pipeline:
- RAS orientation
- 1mm isotropic resampling
- crop to foreground (min-value background)
- save numpy array
"""

import glob
import os
from multiprocessing import Pool

import nibabel as nib
import numpy as np
from monai.transforms import (
    Compose,
    CropForeground,
    ResizeWithPadOrCrop,
    ScaleIntensityRangePercentiles,
)
from tqdm import tqdm
from yucca.functional.preprocessing import preprocess_case_for_training_without_label


# ------------------------------------------------------------
# Path conversion
# ------------------------------------------------------------
def nii_to_npy_path(path):
    if path.endswith(".nii.gz"):
        return path[:-7] + ".npy"
    elif path.endswith(".nii"):
        return path[:-4] + ".npy"
    else:
        raise ValueError(f"Unsupported extension: {path}")


# ------------------------------------------------------------
# Yucca preprocessing wrapper
# ------------------------------------------------------------
transforms = Compose(
    ScaleIntensityRangePercentiles(lower=0.01, upper=99.9, b_min=0.0, b_max=1.0),
    CropForeground(),
    ResizeWithPadOrCrop(spatial_size=[160, 192, 160]),
)


def preprocess_with_yucca(img: nib.Nifti1Image):
    """
    Apply:
    - RAS orientation
    - 1mm isotropic spacing
    - crop to non-background
    """

    images, props = preprocess_case_for_training_without_label(
        images=[img],
        normalization_operation=["no_norm"],  # no intensity normalization
        crop_to_nonzero=True,
        # use min value as background
        background_pixel_value=np.asanyarray(img.dataobj).min(),
        target_orientation="RAS",
        target_spacing=[1.0, 1.0, 1.0],
        target_size=None,
        transpose=[0, 1, 2],
        allow_missing_modalities=False,
    )

    image = images[0]
    if transforms is not None:
        image = transforms(image)

    return images, props


# ------------------------------------------------------------
# Worker
# ------------------------------------------------------------
def process_file(nii_path):
    npy_path = nii_to_npy_path(nii_path)

    if os.path.exists(npy_path):
        return f"[SKIP] Exists: {npy_path}"

    try:
        img = nib.load(nii_path)

        print(f"[INFO] Processing {nii_path}")

        arr, props = preprocess_with_yucca(img)

        np.save(npy_path, arr)

        return f"[OK] {npy_path} | shape={arr.shape}"

    except Exception as e:
        return f"[ERROR] {nii_path}: {e}"


# ------------------------------------------------------------
# File search
# ------------------------------------------------------------
def find_files(root_dir, patterns):
    files = []

    for pattern in patterns:
        search_pattern = os.path.join(root_dir, "**", pattern)
        matched = glob.glob(search_pattern, recursive=True)

        print(f"Pattern '{pattern}' -> {len(matched)} files")
        files.extend(matched)

    return list(dict.fromkeys(files))


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main(root_dir, patterns, n_proc):
    print(f"Searching in: {root_dir}")
    print(f"Patterns: {patterns}")

    files = find_files(root_dir, patterns)

    print(f"Total files: {len(files)}")

    if len(files) == 0:
        return

    with Pool(processes=n_proc) as pool:
        for msg in tqdm(pool.imap_unordered(process_file, files), total=len(files)):
            if msg:
                print(msg)


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Yucca-based NIfTI -> preprocessed NPY conversion"
    )

    parser.add_argument("--source", type=str, required=True)
    parser.add_argument("--patterns", nargs="+", required=True)
    parser.add_argument("--jobs", type=int, default=2)

    args = parser.parse_args()

    print(f"Using {args.jobs} processes")

    main(
        root_dir=args.source,
        patterns=args.patterns,
        n_proc=args.jobs,
    )
