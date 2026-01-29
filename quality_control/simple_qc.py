# Core
# import datetime
import json
from datetime import datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path

# Plotting
import matplotlib.pyplot as plt

# Neuroimaging
import nibabel as nib
import numpy as np

# Data handling
import pandas as pd
from scipy.stats import kurtosis, skew
from tqdm import tqdm


def find_t1w_images(bids_root):
    bids_root = Path(bids_root)
    t1w_files = list(bids_root.rglob("*T1*.nii*"))
    return sorted(t1w_files)


def load_json_sidecar(nifti_path):
    json_path = nifti_path.with_suffix("").with_suffix(".json")
    if json_path.exists():
        with open(json_path, "r") as f:
            return json.load(f)
    return {}


def efc(img, framemask=None, decimals=4):
    if framemask is None:
        framemask = np.zeros_like(img, dtype=np.uint8)

    n_vox = np.sum(1 - framemask)
    # Calculate the maximum value of the EFC (which occurs any time all
    # voxels have the same value)
    efc_max = 1.0 * n_vox * (1.0 / np.sqrt(n_vox)) * np.log(1.0 / np.sqrt(n_vox))

    # Calculate the total image energy
    b_max = np.sqrt((img[framemask == 0] ** 2).sum())

    # Calculate EFC (add 1e-16 to the image data to keep log happy)
    return round(
        float(
            (1.0 / efc_max)
            * np.sum(
                (img[framemask == 0] / b_max)
                * np.log((img[framemask == 0] + 1e-16) / b_max)
            ),
        ),
        decimals,
    )


def extract_t1w_stats_with_metrics(nifti_path, hist_bins=256, compute_metrics=True):
    record = {
        "dataset": str(nifti_path.parents[2].name),
        "path": str(nifti_path),
        "error": None,
    }

    # --- Load image ---
    try:
        img_nii = nib.load(str(nifti_path))
        header = img_nii.header
        data_3d = img_nii.get_fdata()
    except Exception as e:
        record["error"] = str(e)
        return record

    # --- BIDS sidecar ---
    sidecar = load_json_sidecar(nifti_path)

    # --- Geometry / header stats ---
    dims = img_nii.shape[:3]
    voxel_sizes = header.get_zooms()[:3]

    record.update(
        {
            "subject": nifti_path.name.split("_")[0],
            "session": next(
                (p for p in nifti_path.parts if p.startswith("ses-")), None
            ),
            "dim_x": dims[0],
            "dim_y": dims[1],
            "dim_z": dims[2],
            "voxel_x_mm": voxel_sizes[0],
            "voxel_y_mm": voxel_sizes[1],
            "voxel_z_mm": voxel_sizes[2],
            "file_size_mb": nifti_path.stat().st_size / (1024**2),
            "tesla": sidecar.get("MagneticFieldStrength"),
            "manufacturer": sidecar.get("Manufacturer"),
            "model": sidecar.get("ManufacturersModelName"),
        }
    )

    if not compute_metrics:
        return record

    # --- Maskless intensity metrics ---
    data = np.nan_to_num(data_3d, nan=0.0, posinf=0.0, neginf=0.0).reshape(-1)

    data = data[np.isfinite(data)]

    if data.size == 0:
        record["error"] = "empty image"
        return record

    # Robust MAD
    med = np.median(data)
    mad_val = float(np.median(np.abs(data - med)))

    # Histogram-based entropy
    hist, _ = np.histogram(data, bins=hist_bins, density=True)
    probs = hist[hist > 0]
    entropy = float(-np.sum(probs * np.log2(probs))) if probs.size else 0.0

    record.update(
        {
            "n_voxels": int(data.size),
            "n_nonzero": int((data != 0).sum()),
            "nonzero_frac": float((data != 0).mean()),
            "mean": float(np.mean(data)),
            "median": float(med),
            "std": float(np.std(data)),
            "mad": mad_val,
            "kurtosis": float(kurtosis(data)),
            "skewness": float(skew(data)),
            "p01": float(np.percentile(data, 1)),
            "p05": float(np.percentile(data, 5)),
            "p95": float(np.percentile(data, 95)),
            "p99": float(np.percentile(data, 99)),
            "entropy": entropy,
        }
    )

    # --- EFC (best-effort) ---
    try:
        record["efc"] = float(efc(data_3d))
    except Exception:
        record["efc"] = None

    return record


def plot_histogram(df, key, bins=20, dropna=True, eps=1e-8):
    if key not in df.columns:
        raise ValueError(f"Key '{key}' not found in dataframe")

    data = df[key]

    if dropna:
        data = data.dropna()

    if len(data) == 0:
        print(f"[WARN] No data available for '{key}'")
        return

    # Attempt numeric conversion
    is_numeric = True
    try:
        data = pd.to_numeric(data)
    except (ValueError, TypeError):
        is_numeric = False

    plt.figure()

    if is_numeric:
        data_min = data.min()
        data_max = data.max()

        # Zero or near-zero range → constant value
        if np.isclose(data_min, data_max, atol=eps):
            plt.bar([str(round(float(data_min), 4))], [len(data)])
            plt.xlabel(key)
            plt.ylabel("Count")
            plt.title(f"{key} (constant value)")
        else:
            # Safe bin count
            effective_bins = min(bins, len(data))
            plt.hist(data, bins=effective_bins)
            plt.xlabel(key)
            plt.ylabel("Count")
            plt.title(f"Histogram of {key}")
    else:
        # Categorical fallback
        counts = data.value_counts()
        plt.bar(counts.index.astype(str), counts.values)
        plt.xlabel(key)
        plt.ylabel("Count")
        plt.title(f"Distribution of {key}")
        plt.xticks(rotation=45, ha="right")

    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def detect_outliers(
    df,
    metrics=None,
    groupby_cols=("dataset", "tesla", "model"),
    z_thresh=3.0,
    iqr_factor=1.5,
    mad_factor=4,
    file_size_min_mb=4.0,
    max_thickness=1.3,
    min_dimension=100,
):
    """
    Detect outliers in MRI QC metrics using multiple strategies + user-defined criteria.
    Returns a long-form dataframe with one row per detected outlier.
    """

    if metrics is None:
        metrics = [
            # geometry
            "voxel_x_mm",
            "voxel_y_mm",
            "voxel_z_mm",
            "dim_x",
            "dim_y",
            "dim_z",
            "file_size_mb",
            # intensity / QA
            "mean",
            "std",
            "mad",
            "entropy",
            "efc",
            "nonzero_frac",
            "n_voxels",
            "n_nonzero",
            "kurtosis",
            "skewness",
            "p01",
            "p05",
            "p95",
            "p99",
        ]

    outlier_records = []

    grouped = df.groupby(list(groupby_cols), dropna=False)

    for group_key, gdf in grouped:
        for metric in metrics:
            if metric not in gdf.columns:
                continue

            data = gdf[metric].dropna()

            # Need at least a few points
            if data.size < 5:
                continue

            values = data.values

            # ---------- ±3 sigma ----------
            mu = np.mean(values)
            sigma = np.std(values)
            z_mask = (
                np.abs(values - mu) > z_thresh * sigma
                if sigma > 0
                else np.zeros_like(values, dtype=bool)
            )

            # ---------- IQR ----------
            q1 = np.percentile(values, 25)
            q3 = np.percentile(values, 75)
            iqr = q3 - q1
            iqr_mask = (
                (values < (q1 - iqr_factor * iqr)) | (values > (q3 + iqr_factor * iqr))
                if iqr > 0
                else np.zeros_like(values, dtype=bool)
            )

            # ---------- MAD ----------
            med = np.median(values)
            mad = np.median(np.abs(values - med))
            mad_mask = (
                (np.abs(values - med) / mad > mad_factor)
                if mad > 0
                else np.zeros_like(values, dtype=bool)
            )

            # ---------- Additional rules ----------
            additional_mask = np.zeros_like(values, dtype=bool)

            # File size under threshold
            if metric == "file_size_mb":
                additional_mask = values < file_size_min_mb

            # Thickness thresholds
            if metric in ["voxel_x_mm", "voxel_y_mm", "voxel_z_mm"]:
                additional_mask = values > max_thickness

            # Dimension thresholds
            if metric in ["dim_x", "dim_y", "dim_z"]:
                additional_mask = values < min_dimension

            # Combine all masks
            final_mask = z_mask | iqr_mask | mad_mask | additional_mask

            # ---------- Collect ----------
            for idx, is_out in enumerate(final_mask):
                if not is_out:
                    continue

                row = gdf.loc[data.index[idx]]

                outlier_records.append(
                    {
                        "path": row.get("path"),
                        "subject": row.get("subject"),
                        "session": row.get("session"),
                        "metric": metric,
                        "value": values[idx],
                        "group": group_key,
                        "z_sigma": bool(z_mask[idx]),
                        "iqr": bool(iqr_mask[idx]),
                        "mad": bool(mad_mask[idx]),
                        "threshold_rule": bool(additional_mask[idx]),  # NEW COLUMN
                    }
                )

    return pd.DataFrame(outlier_records)


def run_qc_multiprocessing(
    t1w_files, n_jobs=None, chunksize=1, use_multiprocessing=True
):
    if not use_multiprocessing:
        records = []
        for t1w_file in tqdm(t1w_files, desc="Processing T1w images"):
            record = extract_t1w_stats_with_metrics(t1w_file)
            records.append(record)
        return pd.DataFrame(records)

    if n_jobs is None:
        n_jobs = max(1, cpu_count() - 1)

    with Pool(processes=n_jobs) as pool:
        records = list(
            tqdm(
                pool.imap_unordered(
                    extract_t1w_stats_with_metrics, t1w_files, chunksize=chunksize
                ),
                total=len(t1w_files),
                desc="Processing T1w images",
            )
        )

    return pd.DataFrame(records)


def main():
    bids_path = "/run/media/falconnier/Elements1/BIDS_datasets_selection"
    qc_csv_dir = Path("./qc_results")
    qc_csv_dir.mkdir(parents=True, exist_ok=True)
    # iterate over directories
    for dataset_dir in tqdm(Path(bids_path).iterdir(), desc="Datasets"):
        if not dataset_dir.is_dir():
            continue

        print(f"Processing dataset: {dataset_dir.name}")

        t1w_files = find_t1w_images(dataset_dir)
        print(f"Found {len(t1w_files)} T1w images")

        df = run_qc_multiprocessing(t1w_files, 10, 1, True)

        # Save to CSV with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        df.to_csv(
            qc_csv_dir / f"{dataset_dir.name}_t1w_qc_metrics_{timestamp}.csv",
            index=False,
        )


if __name__ == "__main__":
    main()
