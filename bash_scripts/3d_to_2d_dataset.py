from pathlib import Path

import nibabel as nib
import numpy as np


def min_max_normalize(arr):
    lower = np.percentile(arr, 0.01)
    upper = np.percentile(arr, 99.9)
    arr = np.clip(arr, lower, upper)
    if upper > lower:
        arr = (arr - lower) / (upper - lower)
    else:
        arr = np.zeros_like(arr, dtype=np.float32)
    arr = np.clip(arr, 0, 1)
    return arr


def get_middle_slices(volume, normalize=True):
    """
    volume shape assumed: (X, Y, Z)
    Returns raw (normlized) axial, coronal, sagittal slices
    """
    x, y, z = volume.shape

    axial = volume[:, :, z // 2]
    coronal = volume[:, y // 2, :]
    sagittal = volume[x // 2, :, :]

    if normalize:
        axial = min_max_normalize(axial)
        coronal = min_max_normalize(coronal)
        sagittal = min_max_normalize(sagittal)

    return axial, coronal, sagittal


def process_file(src_path: Path, dst_base: Path, root_src: Path):
    rel_path = src_path.relative_to(root_src)

    dst_dir = dst_base / rel_path.parent
    dst_dir.mkdir(parents=True, exist_ok=True)

    if src_path.suffix == ".npy":
        volume = np.load(src_path, mmap_mode="r")
        x, y, z = volume.shape

        axial = np.asarray(volume[:, :, z // 2])
        coronal = np.asarray(volume[:, y // 2, :])
        sagittal = np.asarray(volume[x // 2, :, :])

        base_name = src_path.stem.replace("brain", "")

    elif src_path.suffix == ".gz" and src_path.name.endswith(".nii.gz"):
        img = nib.load(str(src_path))
        proxy = img.dataobj  # ArrayProxy

        x, y, z = img.shape

        axial = np.asanyarray(proxy[:, :, z // 2])
        coronal = np.asanyarray(proxy[:, y // 2, :])
        sagittal = np.asanyarray(proxy[x // 2, :, :])

        base_name = src_path.name.replace(".nii.gz", "").replace("brain", "")

    elif src_path.suffix == ".nii":
        img = nib.load(str(src_path))
        proxy = img.dataobj

        x, y, z = img.shape

        axial = np.asanyarray(proxy[:, :, z // 2])
        coronal = np.asanyarray(proxy[:, y // 2, :])
        sagittal = np.asanyarray(proxy[x // 2, :, :])

        base_name = src_path.stem.replace("brain", "")

    else:
        raise ValueError(f"Unsupported file type: {src_path}")

    np.save(dst_dir / f"{base_name}middle_axial.npy", axial)
    np.save(dst_dir / f"{base_name}middle_coronal.npy", coronal)
    np.save(dst_dir / f"{base_name}middle_sagittal.npy", sagittal)


def convert_bids_dataset(src_dir, dst_dir):
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)

    # for root, _, files in os.walk(src_dir):
    #     for f in files:
    #         if f.endswith("brain.npy"):
    #             # if f.endswith("brain.nii.gz"):
    #             full_path = Path(root) / f
    #             process_file(full_path, dst_dir, src_dir)

    for full_path in src_dir.rglob("*"):
        if full_path.is_file() and full_path.name.endswith("brain.npy"):
            process_file(full_path, dst_dir, src_dir)


if __name__ == "__main__":
    import argparse

    # to convert inplace, jsut use the same path for src and dst
    parser = argparse.ArgumentParser(
        description="Convert BIDS T1w brain.nii.gz to middle-slice .npy arrays (raw values)"
    )
    parser.add_argument("src", type=str, help="Source BIDS dataset path")
    parser.add_argument("dst", type=str, help="Destination dataset path")

    args = parser.parse_args()

    convert_bids_dataset(args.src, args.dst)
