import os
import csv
import numpy as np
import nibabel as nib
from tqdm import tqdm

def compute_dice(mask1, mask2):
    mask1 = mask1.astype(bool)
    mask2 = mask2.astype(bool)

    intersection = np.logical_and(mask1, mask2).sum()
    size1 = mask1.sum()
    size2 = mask2.sum()

    if size1 + size2 == 0:
        return 0.0

    return (2.0 * intersection) / (size1 + size2)


def find_t1w_masks(root_dir):
    matches = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith("T1w_mask.nii.gz"):
                matches.append(os.path.join(dirpath, f))
    return matches


def main(source_root, mni_mask_path, output_csv, threshold=0.7):
    print("🔍 Loading MNI mask...")
    mni_img = nib.load(mni_mask_path)
    mni_data = mni_img.get_fdata() > 0

    print("🔍 Searching for T1w masks...")
    mask_paths = find_t1w_masks(source_root)

    results = []

    for mask_path in tqdm(mask_paths):
        try:
            img = nib.load(mask_path)
            data = img.get_fdata() > 0

            # Resize check (optional but recommended)
            if data.shape != mni_data.shape:
                print(f"⚠️ Skipping (shape mismatch): {mask_path}")
                continue

            dice = compute_dice(data, mni_data)

            flag = "BAD" if dice < threshold else "OK"

            results.append({
                "mask_path": mask_path,
                "dice": dice,
                "flag": flag
            })

        except Exception as e:
            print(f"❌ Error processing {mask_path}: {e}")
            results.append({
                "mask_path": mask_path,
                "dice": None,
                "flag": "ERROR"
            })

    print(f"💾 Writing results to {output_csv}...")

    with open(output_csv, "w", newline="") as csvfile:
        fieldnames = ["mask_path", "dice", "flag"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(results)

    print("✅ Done.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--mni", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threshold", type=float, default=0.92)

    args = parser.parse_args()

    main(
        args.source,
        args.mni,
        args.output,
        args.threshold
    )