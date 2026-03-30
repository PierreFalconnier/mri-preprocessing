import os
import csv
import numpy as np
import nibabel as nib
from tqdm import tqdm
from math import sqrt
# -----------------------
# LABEL GROUPS (SynthSeg)
# https://github.com/BBillot/SynthSeg/blob/master/data/labels%20table.txt
# -----------------------
WM_LABELS = [2, 7, 41, 46]
GM_LABELS = [3, 8, 42, 47]
CSF_LABELS = [24, 4, 5, 14, 15, 43, 44]

def load_nifti(path):
    img = nib.load(path)
    return img.get_fdata(), img

def compute_dice(mask1, mask2):
    mask1 = mask1.astype(bool)
    mask2 = mask2.astype(bool)

    intersection = np.logical_and(mask1, mask2).sum()
    size1 = mask1.sum()
    size2 = mask2.sum()

    if size1 + size2 == 0:
        return 0.0

    return (2.0 * intersection) / (size1 + size2)

# -----------------------
# METRIC HELPERS
# -----------------------

def extract_region(data, seg, labels):
    mask = np.isin(seg, labels)
    values = data[mask]
    values = values[np.isfinite(values)]
    return values

def snr(mu_fg, sigma_fg, n):
    if sigma_fg == 0 or n <= 1:
        return 0.0
    return float(mu_fg / (sigma_fg * np.sqrt(n / (n - 1))))

def cnr(mu_wm, mu_gm, sigma_air):
    if sigma_air == 0:
        return 0
    return abs(mu_wm - mu_gm) / sigma_air

def cjv(mu_wm, mu_gm, sigma_wm, sigma_gm):
    denom = abs(mu_wm - mu_gm)
    if denom == 0:
        return 0
    return (sigma_wm + sigma_gm) / denom

def efc(img):
    img = img - np.min(img)
    if np.max(img) == 0:
        return 0
    img = img / np.max(img)

    flat = img.flatten()
    flat = flat[flat > 0]

    if len(flat) == 0:
        return 0

    p = flat / np.sum(flat)
    entropy = -np.sum(p * np.log(p + 1e-12))

    return entropy

def wm2max(img, mu_wm):
    if np.max(img) == 0:
        return 0
    return np.max(img) / mu_wm

def volume_fraction(seg, labels):
    return np.sum(np.isin(seg, labels)) / seg.size

def summary_stats(values):
    return {
        "mean": float(np.mean(values)) if len(values) > 0 else 0,
        "std": float(np.std(values)) if len(values) > 0 else 0,
        "median": float(np.median(values)) if len(values) > 0 else 0,
    }

# -----------------------
# MAIN
# -----------------------

def find_masks(root_dir):
    matches = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith("T1w_mask.nii.gz"):
                matches.append(os.path.join(dirpath, f))
    return matches


def main(source_root, mni_mask_path, output_csv, threshold=0.92):

    print("🔍 Loading MNI mask...")
    mni_mask, _ = load_nifti(mni_mask_path)

    print("🔍 Searching for masks...")
    mask_paths = find_masks(source_root)[:5]  # Limit to first 100 for testing

    results = []

    for mask_path in tqdm(mask_paths):

        try:
            base = mask_path.replace("mask.nii.gz", "")
            brain_path = base + "brain.nii.gz"
            seg_path = base + "segm.nii.gz"

            if not os.path.exists(brain_path) or not os.path.exists(seg_path):
                print(f"⚠️ Missing files for {mask_path}")
                continue

            mask, _ = load_nifti(mask_path)
            brain, _ = load_nifti(brain_path)
            seg, _ = load_nifti(seg_path)

            # ensure binary
            mask_bin = mask > 0
            mni_bin = mni_mask > 0

            if mask.shape != mni_mask.shape:
                print(f"⚠️ Shape mismatch: {mask_path}")
                continue

            # -----------------------
            # BASIC METRICS
            # -----------------------
            dice = compute_dice(mask_bin, mni_bin)

            wm_vals = extract_region(brain, seg, WM_LABELS)
            gm_vals = extract_region(brain, seg, GM_LABELS)
            csf_vals = extract_region(brain, seg, CSF_LABELS)

            # stats
            mu_wm = np.mean(wm_vals) if len(wm_vals) > 0 else 0
            mu_gm = np.mean(gm_vals) if len(gm_vals) > 0 else 0
            sigma_wm = np.std(wm_vals) if len(wm_vals) > 0 else 0
            sigma_gm = np.std(gm_vals) if len(gm_vals) > 0 else 0

            # approximate background noise
            sigma_air = np.std(brain[brain < np.percentile(brain, 5)])

            # -----------------------
            # MRIQC METRICS
            # -----------------------
            snr_val = snr(mu_wm, sigma_wm)
            cnr_val = cnr(mu_wm, mu_gm, sigma_air)
            cjv_val = cjv(mu_wm, mu_gm, sigma_wm, sigma_gm)
            efc_val = efc(brain)
            wm2max_val = wm2max(brain, mu_wm)

            # volume fractions
            wm_frac = volume_fraction(seg, WM_LABELS)
            gm_frac = volume_fraction(seg, GM_LABELS)
            csf_frac = volume_fraction(seg, CSF_LABELS)

            # -----------------------
            # FLAGGING
            # -----------------------
            flag = "OK"

            if dice < threshold:
                flag = "BAD_DICE"

            if cnr_val > 3.0:
                flag = "BAD_CNR"

            if snr_val < 2.0:
                flag = "BAD_SNR"

            if cjv_val > 0.7:
                flag = "BAD_CJV"
                
            if efc_val > 0.85:
                flag = "BAD_EFC"

            # -----------------------
            # SAVE RESULTS
            # -----------------------
            results.append({
                "mask": mask_path,
                "dice": dice,
                "snr": snr_val,
                "cnr": cnr_val,
                "cjv": cjv_val,
                "efc": efc_val,
                "wm2max": wm2max_val,
                "wm_frac": wm_frac,
                "gm_frac": gm_frac,
                "csf_frac": csf_frac,
                "flag": flag
            })

        except Exception as e:
            print(f"❌ Error: {mask_path} -> {e}")
            results.append({
                "mask": mask_path,
                "dice": None,
                "flag": "ERROR"
            })

    print(f"💾 Writing CSV to {output_csv}")

    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
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

    main(args.source, args.mni, args.output, args.threshold)