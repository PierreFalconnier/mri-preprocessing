# Core
# import datetime
import json
import math
import shutil
from datetime import datetime
from multiprocessing import Pool, cpu_count
from pathlib import Path

import ants

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
    t1w_files = list(bids_root.rglob("*T1w*.nii*"))
    return sorted(t1w_files)


def load_json_sidecar(nifti_path):
    json_path = nifti_path.with_suffix(".json")

    if not json_path.exists():
        return {}

    try:
        with open(json_path, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        return {
            "_json_error": f"JSONDecodeError: {e}",
            "_json_path": str(json_path),
        }
    except Exception as e:
        return {
            "_json_error": f"Exception: {e}",
            "_json_path": str(json_path),
        }


def efc(img, framemask=None, decimals=4):
    if framemask is None:
        framemask = np.zeros_like(img, dtype=np.uint8)

    n_vox = np.sum(1 - framemask)
    # Calculate the maximum value of the EFC (which occurs any time all
    # voxels have the same value)
    efc_max = 1.0 * n_vox * (1.0 / np.sqrt(n_vox)) * np.log(1.0 / np.sqrt(n_vox))

    # Calculate the total image energy
    b_max = np.sqrt((img[framemask == 0] ** 2).sum())
    if (img[framemask == 0] <= 0).any():
        return np.nan

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
    if "sub-" in nifti_path.parents[2].name:  # to handles cases where session dir exist
        dataset_name = str(nifti_path.parents[3].name)
    else:
        dataset_name = str(nifti_path.parents[2].name)

    record = {
        "dataset": dataset_name,
        "path": str(nifti_path),
        "error": None,
    }

    # --- Load image ---
    try:
        img_nii = nib.load(str(nifti_path))
        header = img_nii.header
        data_3d = img_nii.get_fdata()

        sidecar = load_json_sidecar(nifti_path)

        record["tesla"] = sidecar.get("MagneticFieldStrength")
        record["manufacturer"] = sidecar.get("Manufacturer")
        record["model"] = sidecar.get("ManufacturersModelName")

        if "_json_error" in sidecar:
            record["json_error"] = sidecar["_json_error"]
    except Exception as e:
        print(e)
        record["error"] = str(e)
        return record

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

    # keep finite
    data = data[np.isfinite(data)]

    if data.size == 0:
        record["error"] = "empty image"
        return record

    # separate non-zero voxels / low values

    # nz = data[data != 0]
    low = np.percentile(data, 1)
    nz = data[data > low]

    if nz.size == 0:
        record["error"] = "all-zero image"
        return record

    # Robust MAD
    med = np.median(nz)
    mad_val = float(np.median(np.abs(nz - med)))

    # Histogram-based entropy (non-zero only)
    hist, _ = np.histogram(nz, bins=hist_bins, density=True)
    probs = hist[hist > 0]
    entropy = float(-np.sum(probs * np.log2(probs))) if probs.size else 0.0

    record.update(
        {
            # geometry-related counts
            "n_voxels": int(data.size),
            "n_nonzero": int(nz.size),
            "nonzero_frac": float(nz.size / data.size),
            "min": float(np.min(data)),
            "max": float(np.max(data)),
            # intensity stats (non-zero)
            "mean": float(np.mean(nz)),
            "median": float(med),
            "std": float(np.std(nz)),
            "mad": mad_val,
            "kurtosis": float(kurtosis(nz)),
            "skewness": float(skew(nz)),
            "p01": float(np.percentile(nz, 1)),
            "p05": float(np.percentile(nz, 5)),
            "p95": float(np.percentile(nz, 95)),
            "p99": float(np.percentile(nz, 99)),
            "entropy": entropy,
        }
    )

    # --- EFC (best-effort) ---
    try:
        record["efc"] = float(efc(data_3d))
    except Exception:
        record["efc"] = None

    return record


def plot_histograms_grid(
    df,
    keys,
    bins=30,
    dropna=True,
    max_cols=4,
    figsize_per_plot=(4, 3),
    percentile_low=1,
    percentile_high=99,
):
    """
    Plot histograms for multiple dataframe columns in a single figure,
    with percentile markers for numeric variables.
    """

    keys = [k for k in keys if k in df.columns]
    if not keys:
        raise ValueError("None of the provided keys exist in the dataframe")

    n = len(keys)
    n_cols = min(max_cols, n)
    n_rows = math.ceil(n / n_cols)

    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(figsize_per_plot[0] * n_cols, figsize_per_plot[1] * n_rows),
        squeeze=False,
    )

    axes = axes.flatten()

    for ax, key in zip(axes, keys):
        data = df[key]

        if dropna:
            data = data.dropna()

        if data.empty:
            ax.set_title(f"{key} (no data)")
            ax.axis("off")
            continue

        # Try numeric conversion
        is_numeric = True
        try:
            data = pd.to_numeric(data)
        except Exception:
            is_numeric = False

        if is_numeric:
            values = data.values

            ax.hist(values, bins=min(bins, len(values)))
            ax.set_ylabel("Count")

            # Percentiles
            p_low = np.percentile(values, percentile_low)
            p_high = np.percentile(values, percentile_high)

            ax.axvline(p_low, linestyle="--", linewidth=1)
            ax.axvline(p_high, linestyle="--", linewidth=1)

            ax.text(
                p_low,
                ax.get_ylim()[1] * 0.9,
                f"{percentile_low}%",
                rotation=90,
                va="top",
                ha="right",
            )
            ax.text(
                p_high,
                ax.get_ylim()[1] * 0.9,
                f"{percentile_high}%",
                rotation=90,
                va="top",
                ha="left",
            )

        else:
            counts = data.value_counts()
            ax.bar(counts.index.astype(str), counts.values)
            ax.tick_params(axis="x", rotation=45)

        ax.set_title(key)
        ax.grid(True, alpha=0.3)

    # Hide unused subplots
    for ax in axes[len(keys) :]:
        ax.axis("off")

    fig.tight_layout()
    plt.show()


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
    z_thresh=5,
    iqr_factor=2.5,
    mad_factor=6,
    file_size_min_mb=4.0,
    max_thickness=1.25,
    min_dimension=120,
):
    """
    Detect outliers in MRI QC metrics using multiple strategies + user-defined criteria.
    Returns a long-form dataframe with one row per detected outlier.
    default settings are quite strict to avoid false positives.
    """

    if metrics is None:
        metrics = [
            # "voxel_x_mm",
            # "voxel_y_mm",
            # "voxel_z_mm",
            # "dim_x",
            # "dim_y",
            # "dim_z",
            "file_size_mb",
            # "min",
            "max",
            "median",
            "mean",
            "std",
            "mad",
            "entropy",
            "efc",
            "nonzero_frac",
            # "n_voxels",
            "n_nonzero",
            "kurtosis",
            "skewness",
            # "p01",
            # "p05",
            # "p95",
            # "p99",
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

            # ---------- sigma ----------
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

            # ---------- Percentile-based ----------
            p01 = np.percentile(values, 1)
            p99 = np.percentile(values, 99)

            percentile_mask = (values < p01) | (values > p99)

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
            final_mask = (
                z_mask | iqr_mask | mad_mask | additional_mask | percentile_mask
            )

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
                        "percentile": bool(percentile_mask[idx]),
                        "threshold_rule": bool(additional_mask[idx]),
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


def compute_stats(bids_path="/run/media/falconnier/Elements/BIDS_datasets_selection"):
    n_processes = 6
    dirpath = Path(__file__).parent.resolve()
    qc_csv_dir = dirpath / "qc_results"

    print("The qc results will be saved to:", qc_csv_dir)
    qc_csv_dir.mkdir(parents=True, exist_ok=True)
    # iterate over directories
    for dataset_dir in tqdm(Path(bids_path).iterdir(), desc="Datasets"):
        if not dataset_dir.is_dir():
            continue

        # if a csv file already exists for this dataset, skip it
        existing_csvs = list(
            qc_csv_dir.glob(f"{dataset_dir.name}_t1w_qc_metrics_*.csv")
        )
        if existing_csvs:
            print(f"Skipping dataset (CSV exists): {dataset_dir.name}")
            continue

        print(f"Processing dataset: {dataset_dir.name}")

        t1w_files = find_t1w_images(dataset_dir)
        print(f"Found {len(t1w_files)} T1w images")

        df = run_qc_multiprocessing(t1w_files, n_processes, 1, True)

        # Save to CSV with timestamp
        print(f"Saving QC metrics to {qc_csv_dir}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        df.to_csv(
            qc_csv_dir / f"{dataset_dir.name}_t1w_qc_metrics_{timestamp}.csv",
            index=False,
        )


def compute_detect_outliers():
    dirpath = Path(__file__).parent.resolve()
    qc_csv_dir = dirpath / "qc_results"
    qc_csv_outlier_dir = dirpath / "qc_outliers"

    shutil.rmtree(qc_csv_outlier_dir, ignore_errors=True)
    qc_csv_outlier_dir.mkdir(parents=True, exist_ok=True)

    qc_csv_files = list(qc_csv_dir.glob("*_t1w_qc_metrics_*.csv"))
    for qc_csv_file in qc_csv_files:
        print(f"Detecting outliers in: {qc_csv_file.name}")
        df = pd.read_csv(qc_csv_file)
        outliers_df = detect_outliers(df)

        # Save outliers to CSV
        outlier_csv_path = qc_csv_outlier_dir / (qc_csv_file.stem + "_outliers.csv")
        outliers_df.to_csv(outlier_csv_path, index=False)
        print(f"Outliers saved to: {outlier_csv_path}")


def visual_check_stats():
    dirpath = Path(__file__).parent.resolve()

    # qc_csv_outlier_dir = dirpath / "qc_outliers"
    # qc_csv_files = list(qc_csv_outlier_dir.glob("*_outliers.csv"))

    qc_csv_outlier_dir = dirpath / "qc_results"
    qc_csv_files = list(qc_csv_outlier_dir.glob("*.csv"))

    for qc_csv_file in qc_csv_files:
        print(f"CSV FILE: {qc_csv_file.name}")

        df = pd.read_csv(qc_csv_file)
        metrics_to_plot = [
            "tesla",
            "dim_x",
            "dim_y",
            "dim_z",
            "voxel_x_mm",
            "voxel_y_mm",
            "voxel_z_mm",
            "file_size_mb",
            "n_voxels",
            "n_nonzero",
            "nonzero_frac",
            "min",
            "max",
            "mean",
            "median",
            "std",
            "mad",
            "kurtosis",
            "skewness",
            "p01",
            "p05",
            "p95",
            "p99",
            "entropy",
            "efc",
        ]

        plot_histograms_grid(df, metrics_to_plot, bins=40)


# def trunc_path(path_str):
#     path_str.split("/")[-3:]


def outlier_visual_check_image():
    dirpath = Path(__file__).parent.resolve()
    qc_csv_outlier_dir = dirpath / "qc_outliers"
    qc_csv_files = list(qc_csv_outlier_dir.glob("*_outliers.csv"))
    for qc_csv_file in qc_csv_files:
        # print(f"CSV FILE: {qc_csv_file.name}")

        df = pd.read_csv(qc_csv_file)
        # print(df[df["z_sigma"] | df["threshold_rule"]]["path"].nunique())
        path_df = df[df["z_sigma"] | df["threshold_rule"]]["path"]
        path_df = df[df["threshold_rule"]]["path"]
        path_df = df[df["z_sigma"]]["path"]
        # drop duplicates
        path_df = path_df.drop_duplicates()
        path_list = list(path_df)

        if len(path_list) == 0:
            continue

        path1 = Path(path_list[0])
        path2 = Path(str(path1).replace("Elements1", "Elements"))
        chosen_path = path2 if path2.exists() else path1
        img = ants.image_read(str(chosen_path))
        # ants.plot(img, axis=0)
        # ants.plot(img, axis=1)
        # ants.plot(img, axis=2)

        arr = img.numpy()
        print(arr.shape)
        print(chosen_path)

        fig, axes = plt.subplots(1, 3, figsize=(12, 4))

        axes[0].imshow(arr[arr.shape[0] // 2, :, :], cmap="gray")
        axes[0].set_title("axis 0")

        axes[1].imshow(arr[:, arr.shape[1] // 2, :], cmap="gray")
        axes[1].set_title("axis 1")

        axes[2].imshow(arr[:, :, arr.shape[2] // 2], cmap="gray")
        axes[2].set_title("axis 2")

        for ax in axes:
            ax.axis("off")

        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    compute_stats()
    compute_detect_outliers()
    # visual_check_stats()
    # outlier_visual_check_image()

    # dirpath = Path.cwd()

    # qc_csv_outlier_dir = dirpath / "qc_outliers"
    # qc_csv_files = list(qc_csv_outlier_dir.glob("*_outliers.csv"))
    # outliers = pd.concat(pd.read_csv(f) for f in qc_csv_files)
    # outliers.reset_index(drop=True, inplace=True)

    # # filter if threshold_rule or z_sigma is true
    # outliers_filtered = outliers[outliers["threshold_rule"] | outliers["z_sigma"]]
    # # in the path column, split with "/" and remove the 5 first parts
    # outliers_filtered["path"] = outliers_filtered["path"].apply(
    #     lambda path_str: "/".join(path_str.split("/")[6:])
    # )
    # # remove duplicates
    # outliers_filtered = outliers_filtered.drop_duplicates(subset=["path"])
    # # save the filtered outliers to a csv file
    # outliers_filtered.to_csv("filtered_outliers_before_preprocessing.csv", index=False)
    # # save the paths to a text file
    # outliers_filtered["path"].to_csv(
    #     "filtered_outliers_paths_before_preprocessing.txt", index=False, header=False
    # )
