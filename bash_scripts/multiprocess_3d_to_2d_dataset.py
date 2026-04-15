import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import nibabel as nib
import numpy as np


def process_file(args):
    """
    Wrapped for multiprocessing (must be picklable)
    """
    src_path, dst_base, root_src = args

    rel_path = src_path.relative_to(root_src)
    dst_dir = dst_base / rel_path.parent
    dst_dir.mkdir(parents=True, exist_ok=True)

    img = nib.load(str(src_path))

    # shape without loading full data
    x, y, z = img.shape
    proxy = img.dataobj

    # load only needed slices
    axial = np.asanyarray(proxy[:, :, z // 2])
    coronal = np.asanyarray(proxy[:, y // 2, :])
    sagittal = np.asanyarray(proxy[x // 2, :, :])

    base_name = src_path.name.replace("brain.nii.gz", "")

    np.save(dst_dir / f"{base_name}axial.npy", axial)
    np.save(dst_dir / f"{base_name}coronal.npy", coronal)
    np.save(dst_dir / f"{base_name}sagittal.npy", sagittal)

    return str(src_path)  # optional (for logging)


def convert_bids_dataset(src_dir, dst_dir, num_workers=None):
    src_dir = Path(src_dir)
    dst_dir = Path(dst_dir)

    # Collect all files first (important for multiprocessing)
    tasks = []
    for root, _, files in os.walk(src_dir):
        for f in files:
            if f.endswith("brain.nii.gz"):
                full_path = Path(root) / f
                tasks.append((full_path, dst_dir, src_dir))

    print(f"Found {len(tasks)} files")

    # Use all CPUs by default
    if num_workers is None:
        num_workers = os.cpu_count()

    print(f"Using {num_workers} workers")

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(process_file, t) for t in tasks]

        for i, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()  # noqa: F841
                if i % 50 == 0:
                    print(f"Processed {i}/{len(tasks)}")
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert BIDS T1w brain.nii.gz to middle-slice .npy arrays (multiprocessing)"
    )
    parser.add_argument("src", type=str, help="Source BIDS dataset path")
    parser.add_argument("dst", type=str, help="Destination dataset path")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: CPU count)",
    )

    args = parser.parse_args()

    convert_bids_dataset(args.src, args.dst, args.workers)
