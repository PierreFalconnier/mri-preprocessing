import csv
import os

import nibabel as nib
import numpy as np
import pandas as pd
import plotly.express as px
from tqdm import tqdm

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


def cnr(mu_wm, mu_gm, sigma_air, sigma_wm, sigma_gm):
    denom = np.sqrt(sigma_air**2 + sigma_gm**2 + sigma_wm**2)
    if denom == 0:
        return 0.0
    return float(abs(mu_wm - mu_gm) / denom)


def cjv(mu_wm, mu_gm, sigma_wm, sigma_gm):
    denom = abs(mu_wm - mu_gm)
    if denom == 0:
        return 0.0
    return float((sigma_wm + sigma_gm) / denom)


def efc(img):
    img = img.astype(np.float64)

    n_vox = img.size
    efc_max = n_vox * (1.0 / np.sqrt(n_vox)) * np.log(1.0 / np.sqrt(n_vox))

    b_max = np.sqrt((img**2).sum())

    return float(
        (1.0 / efc_max) * np.sum((img / b_max) * np.log((img + 1e-16) / b_max))
    )


def wm2max(img, mu_wm):
    p995 = np.percentile(img.reshape(-1), 99.95)
    if p995 == 0:
        return 0.0
    return float(mu_wm / p995)


DIETRICH_FACTOR = 0.6551364


def snr_dietrich(mu_fg, sigma_air):
    if sigma_air < 1e-6:
        return -1.0
    return float(DIETRICH_FACTOR * mu_fg / sigma_air)


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


def plot_metrics(results, output_html="qc_plots.html"):
    df = pd.DataFrame(results)

    metrics = [
        "dice",
        "snr_wm",
        "snr_gm",
        "snr_csf",
        "cnr",
        "cjv",
        "efc",
        "wm2max",
    ]

    figs = []

    for metric in metrics:
        if metric not in df.columns:
            continue

        fig = px.strip(
            df,
            y=metric,
            hover_data=["mask"],
            color="flag",
            title=f"{metric} distribution",
        )

        fig.update_traces(jitter=0.4, marker=dict(size=8))
        figs.append(fig)

    # combine into one HTML
    with open(output_html, "w") as f:
        for fig in figs:
            f.write(fig.to_html(full_html=False, include_plotlyjs="cdn"))

    print(f"📊 Interactive QC plots saved to {output_html}")


def main(source_root, mni_mask_path, output_csv, threshold=0.92):

    print("Loading MNI mask...")
    mni_mask, _ = load_nifti(mni_mask_path)

    print("Searching for masks...")
    mask_paths = find_masks(source_root)  # Limit to first 500 for testing

    results = []

    for mask_path in tqdm(mask_paths):
        try:
            base = mask_path.replace("mask.nii.gz", "")
            brain_path = base + "brain.nii.gz"
            seg_path = base + "segm.nii.gz"

            if not os.path.exists(brain_path) or not os.path.exists(seg_path):
                print(f"Missing files for {mask_path}")
                continue

            mask, _ = load_nifti(mask_path)
            brain, _ = load_nifti(brain_path)
            seg, _ = load_nifti(seg_path)

            # ensure binary
            mask_bin = mask > 0
            mni_bin = mni_mask > 0

            if mask.shape != mni_mask.shape:
                print(f"Shape mismatch: {mask_path}")
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
            mu_csf = np.mean(csf_vals) if len(csf_vals) > 0 else 0
            sigma_wm = np.std(wm_vals) if len(wm_vals) > 0 else 0
            sigma_gm = np.std(gm_vals) if len(gm_vals) > 0 else 0
            sigma_csf = np.std(csf_vals) if len(csf_vals) > 0 else 0

            # approximate background noise
            air_mask = mask == 0
            air_vals = brain[air_mask]

            sigma_air = np.std(air_vals)
            # mad_air = np.median(np.abs(air_vals - np.median(air_vals)))

            # -----------------------
            # MRIQC METRICS
            # -----------------------
            # n = number of voxels in foreground mask.
            n_wm = np.sum(np.isin(seg, WM_LABELS))
            n_gm = np.sum(np.isin(seg, GM_LABELS))
            n_csf = np.sum(np.isin(seg, CSF_LABELS))
            snr_wm = snr(mu_wm, sigma_wm, n_wm)
            snr_gm = snr(mu_gm, sigma_gm, n_gm)
            snr_csf = snr(mu_csf, sigma_csf, n_csf)  # using CSF stats for CSF SNR
            cnr_val = cnr(mu_wm, mu_gm, sigma_air, sigma_wm, sigma_gm)

            cjv_val = cjv(mu_wm, mu_gm, sigma_wm, sigma_gm)
            efc_val = efc(brain)
            wm2max_val = wm2max(brain, mu_wm)

            # volume fractions
            total = np.sum(seg > 0)
            wm_frac = np.sum(np.isin(seg, WM_LABELS)) / total
            gm_frac = np.sum(np.isin(seg, GM_LABELS)) / total
            csf_frac = np.sum(np.isin(seg, CSF_LABELS)) / total

            # -----------------------
            # FLAGGING
            # -----------------------
            flag = "OK"

            if dice < threshold:
                flag = "BAD_DICE"

            # if cnr_val < .5:
            #     flag = "BAD_CNR"

            if snr_wm < 6.0:
                flag = "BAD_SNR_WM"

            if snr_gm < 3.0:
                flag = "BAD_SNR_GM"

            if snr_csf < 1.0:
                flag = "BAD_SNR_CSF"

            if cjv_val > 0.85:
                flag = "BAD_CJV"

            if 0.3 < efc_val:
                flag = "BAD_EFC"

            if wm2max_val < 0.3:
                flag = "BAD_WM2MAX"

            # -----------------------
            # SAVE RESULTS
            # -----------------------
            results.append(
                {
                    "mask": mask_path,
                    "dice": dice,
                    # MRIQC core
                    "snr_wm": snr_wm,
                    "snr_gm": snr_gm,
                    "snr_csf": snr_csf,
                    # "snr_dietrich": snr_d,
                    "cnr": cnr_val,
                    "cjv": cjv_val,
                    "efc": efc_val,
                    "wm2max": wm2max_val,
                    # anatomy
                    "wm_frac": wm_frac,
                    "gm_frac": gm_frac,
                    "csf_frac": csf_frac,
                    # optional
                    "sigma_air": sigma_air,
                    "flag": flag,
                }
            )
        except Exception as e:
            print(f"❌ Error: {mask_path} -> {e}")
            results.append({"mask": mask_path, "dice": None, "flag": "ERROR"})

    print(f"Writing CSV to {output_csv}")

    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    plot_metrics(results, output_csv.replace(".csv", ".html"))

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
