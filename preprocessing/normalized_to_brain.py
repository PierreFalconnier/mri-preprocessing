import glob
import os

import nibabel as nib


def process_file(norm_path):
    # Derive mask and output paths
    mask_path = norm_path.replace("normalized", "mask")
    brain_path = norm_path.replace("normalized", "brain")

    if not os.path.exists(mask_path):
        print(f"[WARNING] Mask not found for {norm_path}")
        return

    if os.path.exists(brain_path):
        print(f"[SKIP] Already exists: {brain_path}")
        return

    try:
        # Load images
        norm_img = nib.load(norm_path)
        mask_img = nib.load(mask_path)

        normalized_arr = norm_img.get_fdata()
        mask_arr = mask_img.get_fdata()

        # Apply masking
        brain_arr = normalized_arr.copy()
        brain_arr[mask_arr == 0] = brain_arr.min()

        # Save output
        brain_img = nib.Nifti1Image(brain_arr, norm_img.affine, norm_img.header)
        nib.save(brain_img, brain_path)

        print(f"[OK] Saved: {brain_path}")

    except Exception as e:
        print(f"[ERROR] Failed for {norm_path}: {e}")


def main(root_dir):
    # Find all matching files recursively
    pattern = os.path.join(root_dir, "**", "*T1w_normalized.nii.gz")
    files = glob.glob(pattern, recursive=True)

    print(f"Found {len(files)} files")

    for f in files:
        process_file(f)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create brain-masked images from normalized MRI"
    )
    parser.add_argument("root_dir", type=str, help="Root directory to search")

    args = parser.parse_args()

    main(args.root_dir)
