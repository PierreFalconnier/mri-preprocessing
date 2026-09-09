"""Final export step: RAS-orient, resample to 1mm isotropic, crop to
foreground (background = min value), min-max normalize, and save as .npy
next to the source .nii.gz -- ready to be memory-mapped for training.

Moved from `bash_scripts/add_npy_from_nii.py`, logic unchanged. Requires
the `yucca` package.
"""

from __future__ import annotations

import glob
import os
from multiprocessing import Pool

import nibabel as nib
import numpy as np
from tqdm import tqdm
from yucca.functional.preprocessing import preprocess_case_for_training_without_label


def nii_to_npy_path(path: str) -> str:
    if path.endswith(".nii.gz"):
        return path[:-7] + ".npy"
    if path.endswith(".nii"):
        return path[:-4] + ".npy"
    raise ValueError(f"Unsupported extension: {path}")


def min_max_normalize(arr: np.ndarray) -> np.ndarray:
    lower = np.percentile(arr, 0.01)
    upper = np.percentile(arr, 99.9)
    arr = np.clip(arr, lower, upper)
    arr = (arr - lower) / (upper - lower) if upper > lower else np.zeros_like(arr, dtype=np.float32)
    return np.clip(arr, 0, 1)


def preprocess_with_yucca(img: nib.Nifti1Image, target_size=(160, 192, 160)):
    images, props = preprocess_case_for_training_without_label(
        images=[img],
        normalization_operation=["no_norm"],
        crop_to_nonzero=True,
        background_pixel_value=np.asanyarray(img.dataobj).min(),
        target_orientation="RAS",
        target_spacing=[1.0, 1.0, 1.0],
        target_size=list(target_size),
        transpose=[0, 1, 2],
        allow_missing_modalities=False,
    )
    return min_max_normalize(images[0]), props


def process_file(nii_path: str) -> str:
    npy_path = nii_to_npy_path(nii_path)
    if os.path.exists(npy_path):
        return f"[SKIP] Exists: {npy_path}"
    try:
        img = nib.load(nii_path)
        arr, _ = preprocess_with_yucca(img)
        np.save(npy_path, arr)
        return f"[OK] {npy_path} | shape={arr.shape}, min={arr.min():.4f}, max={arr.max():.4f}"
    except Exception as e:
        return f"[ERROR] {nii_path}: {e}"


def find_files(root_dir: str, patterns: list[str]) -> list[str]:
    files: list[str] = []
    for pattern in patterns:
        matched = glob.glob(os.path.join(root_dir, "**", pattern), recursive=True)
        print(f"Pattern '{pattern}' -> {len(matched)} files")
        files.extend(matched)
    return list(dict.fromkeys(files))


def export_dataset_to_npy(root_dir: str, patterns: list[str], n_proc: int = 2) -> None:
    files = find_files(root_dir, patterns)
    print(f"Total files: {len(files)}")
    if not files:
        return
    with Pool(processes=n_proc) as pool:
        for msg in tqdm(pool.imap_unordered(process_file, files), total=len(files)):
            if msg:
                print(msg)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NIfTI -> preprocessed NPY conversion")
    parser.add_argument("--source", required=True)
    parser.add_argument("--patterns", nargs="+", required=True)
    parser.add_argument("--jobs", type=int, default=2)
    args = parser.parse_args()
    export_dataset_to_npy(args.source, args.patterns, args.jobs)
