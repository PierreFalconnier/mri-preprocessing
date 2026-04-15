import glob
import os
from multiprocessing import Pool, cpu_count

import nibabel as nib
from tqdm import tqdm


def process_file(norm_path):
    mask_path = norm_path.replace("normalized", "mask")
    brain_path = norm_path.replace("normalized", "brain")

    if not os.path.exists(mask_path):
        return f"[WARNING] Mask not found: {mask_path}"

    if os.path.exists(brain_path):
        return f"[SKIP] Exists: {brain_path}"

    try:
        norm_img = nib.load(norm_path)
        mask_img = nib.load(mask_path)

        normalized_arr = norm_img.get_fdata()
        mask_arr = mask_img.get_fdata()

        # Safety: ensure shapes match
        if normalized_arr.shape != mask_arr.shape:
            return f"[ERROR] Shape mismatch: {norm_path}"

        # Apply mask
        brain_arr = normalized_arr.copy()
        brain_arr[mask_arr < 0.5] = brain_arr.min()

        brain_img = nib.Nifti1Image(brain_arr, norm_img.affine, norm_img.header)
        nib.save(brain_img, brain_path)

        return f"[OK] {brain_path}"

    except Exception as e:
        return f"[ERROR] {norm_path}: {e}"


def main(root_dir, n_proc):
    pattern = "*T1w_normalized.nii.gz"
    print(f"Looking for files in {root_dir} with pattern {pattern}...")

    pattern = os.path.join(root_dir, "**", pattern)
    files = glob.glob(pattern, recursive=True)

    print(f"Found {len(files)} files")

    if len(files) == 0:
        return

    with Pool(processes=n_proc) as pool:
        for msg in tqdm(pool.imap_unordered(process_file, files), total=len(files)):
            if msg:
                print(msg)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create brain-masked images from normalized MRI (multiprocessing)"
    )
    parser.add_argument("--source", type=str, help="Root directory to search")
    parser.add_argument(
        "--jobs",
        type=int,
        default=cpu_count(),
        help="Number of processes (default: all cores)",
    )

    args = parser.parse_args()
    print("Using multiprocessing with", args.jobs, "processes")
    main(args.source, args.jobs)
