#!/usr/bin/env python3

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
from scipy.ndimage import binary_closing, binary_opening
from skimage.filters import threshold_otsu
from tqdm import tqdm

# Optional ITK-based N4 (better but optional)
try:
    import itk

    USE_ITK = True
except ImportError:
    USE_ITK = False


def n4_correction(data):
    if not USE_ITK:
        return data

    image = itk.image_from_array(data.astype(np.float32))
    image = itk.cast_image_filter(image, itk.Image[itk.F, 3])
    mask = itk.OtsuThreshold(image, 0, 1, 200)
    corrector = itk.N4BiasFieldCorrectionImageFilter.New(image, mask)
    corrector.Update()
    return itk.array_from_image(corrector.GetOutput())


def brain_mask(data):
    thresh = threshold_otsu(data[data > 0])
    mask = data > thresh
    mask = binary_opening(mask, iterations=2)
    mask = binary_closing(mask, iterations=2)
    return mask


def qc_metrics(data, mask, voxel_volume):
    brain_voxels = data[mask]
    bg_voxels = data[~mask]

    brain_volume = mask.sum() * voxel_volume
    snr_proxy = brain_voxels.mean() / (bg_voxels.std() + 1e-6)

    p2, p98 = np.percentile(brain_voxels, [2, 98])

    return {
        "brain_volume_mm3": round(float(brain_volume), 2),
        "snr_proxy": round(float(snr_proxy), 2),
        "p02_intensity": round(float(p2), 2),
        "p98_intensity": round(float(p98), 2),
    }


def qc_snapshot(data, mask, out_png):
    z, y, x = np.array(data.shape) // 2

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    slices = [
        (data[z, :, :], mask[z, :, :]),
        (data[:, y, :], mask[:, y, :]),
        (data[:, :, x], mask[:, :, x]),
    ]

    for ax, (img, msk) in zip(axes, slices):
        ax.imshow(img.T, cmap="gray", origin="lower")
        ax.contour(msk.T, colors="r", linewidths=0.5)
        ax.axis("off")

    plt.tight_layout()
    plt.savefig(out_png, dpi=150)
    plt.close()


def run_qc(t1w_path, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)

    img = nib.load(t1w_path)
    data = img.get_fdata()
    voxel_volume = np.prod(img.header.get_zooms())

    data = n4_correction(data)
    mask = brain_mask(data)

    metrics = qc_metrics(data, mask, voxel_volume)

    qc_snapshot(
        data,
        mask,
        out_dir / f"{t1w_path.stem}_qc.png",
    )

    with open(out_dir / f"{t1w_path.stem}_qc.json", "w") as f:
        json.dump(metrics, f, indent=2)


def main(bids_root, out_root):
    t1ws = list(Path(bids_root).rglob("*_T1w.nii.gz"))
    if not t1ws:
        print("No T1w files found")
        sys.exit(1)

    for t1w in tqdm(t1ws, desc="QC T1w"):
        sub = t1w.stem.replace("_T1w", "")
        run_qc(t1w, Path(out_root) / sub)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: qc_t1w_fast.py <bids_dir> <qc_out>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
