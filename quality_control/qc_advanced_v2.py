"""The V2 adds automatic outlier detection"""

import html
import os
from pathlib import Path

import matplotlib.pyplot as plt
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
# OUTLIER DETECTION
# -----------------------


def detect_outliers(df, dice_threshold=0.92, z_thresh=3.5):
    """
    Robust outlier detection using Median + MAD
    """
    df = df.copy()

    metrics = [
        "snr_wm",
        "snr_gm",
        "snr_csf",
        "cnr",
        "cjv",
        # "efc",
        "wm2max",
    ]

    df["flag"] = "OK"

    # --- Dice rule (separate)
    df.loc[df["dice"] < dice_threshold, "flag"] = "OUTLIER_DICE"

    # --- MAD-based outliers
    for metric in metrics:
        if metric not in df.columns:
            continue

        vals = df[metric].astype(float)

        median = np.nanmedian(vals)
        mad = np.nanmedian(np.abs(vals - median))

        if mad < 1e-6:
            continue

        # for a normal distribution, MAD is about 0.67449 σ
        z = 0.67449 * (vals - median) / mad
        df.loc[np.abs(z) > z_thresh, "flag"] = f"OUTLIER_{metric.upper()}"

    # --- Missing / error cases
    df.loc[df["dice"].isna(), "flag"] = "OUTLIER_MISSING"

    return df


# -----------------------
# OUTLIER VIZUALISATION
# -----------------------


def create_mosaic(image, title="", save_path=None):
    """
    Simple 3-view mosaic (axial, sagittal, coronal)
    """
    z, y, x = np.array(image.shape) // 2

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    axes[0].imshow(image[z, :, :].T, cmap="gray", origin="lower")
    axes[0].set_title("Axial")

    axes[1].imshow(image[:, y, :].T, cmap="gray", origin="lower")
    axes[1].set_title("Coronal")

    axes[2].imshow(image[:, :, x].T, cmap="gray", origin="lower")
    axes[2].set_title("Sagittal")

    for ax in axes:
        ax.axis("off")

    plt.suptitle(title)

    if save_path:
        plt.savefig(save_path, bbox_inches="tight")
        plt.close()
    else:
        plt.show()


def generate_outlier_mosaics(df, output_dir="outliers_mosaic"):
    os.makedirs(output_dir, exist_ok=True)

    outliers = df[df["flag"] != "OK"]

    print(f"Generating mosaics for {len(outliers)} outliers...")
    print(f"mosaics will be saved in {output_dir}")

    for _, row in tqdm(outliers.iterrows(), total=len(outliers)):
        try:
            mask_path = row["mask"]
            base = mask_path.replace("mask.nii.gz", "")
            brain_path = base + "brain.nii.gz"

            if not os.path.exists(brain_path):
                continue

            brain, _ = load_nifti(brain_path)

            fname = os.path.basename(mask_path).replace(".nii.gz", ".png")
            save_path = os.path.join(output_dir, fname)

            create_mosaic(
                brain,
                title=f"{row['flag']}",
                save_path=save_path,
            )

        except Exception as e:
            print(f"Failed mosaic: {row['mask']} -> {e}")


def plot_metrics(results, output_html="qc_plots.html"):
    df = pd.DataFrame(results)

    metrics = [
        "dice",
        "snr_wm",
        "snr_gm",
        "snr_csf",
        "cnr",
        "cjv",
        # "efc",
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

    print(f"Interactive QC plots saved to {output_html}")


def create_html_gallery(df, mosaic_dir, output_html):
    """
    Create an interactive HTML gallery of mosaics with metrics.
    """

    mosaic_dir = Path(mosaic_dir)

    rows_html = []

    for _, row in df.iterrows():
        mask_path = row["mask"]
        flag = row.get("flag", "OK")

        fname = Path(mask_path).stem.replace(".nii", "") + ".png"
        img_path = mosaic_dir / fname

        if not img_path.exists():
            continue

        # escape text
        mask_safe = html.escape(mask_path)

        # compact metrics display
        metrics_str = "<br>".join(
            [
                f"dice: {row.get('dice', 'NA'):.3f}"
                if pd.notna(row.get("dice"))
                else "dice: NA",
                f"snr_wm: {row.get('snr_wm', 0):.2f}",
                f"snr_gm: {row.get('snr_gm', 0):.2f}",
                f"cnr: {row.get('cnr', 0):.2f}",
                f"cjv: {row.get('cjv', 0):.2f}",
                f"efc: {row.get('efc', 0):.3f}",
            ]
        )

        # color by flag
        color = "#2ecc71" if flag == "OK" else "#e74c3c"

        card = f"""
        <div class="card" style="border-color:{color}">
            <a href="{img_path.name}" target="_blank">
                <img src="{img_path.name}" loading="lazy">
            </a>
            <div class="info">
                <b style="color:{color}">{flag}</b><br>
                <small>{mask_safe}</small><br><br>
                {metrics_str}
            </div>
        </div>
        """

        rows_html.append(card)

    # -----------------------
    # HTML template
    # -----------------------
    html_content = f"""
    <html>
    <head>
        <title>QC Mosaic Gallery</title>
        <style>
            body {{
                font-family: Arial;
                background: #111;
                color: #eee;
                margin: 0;
                padding: 20px;
            }}
            h1 {{
                text-align: center;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 15px;
            }}
            .card {{
                background: #222;
                border: 3px solid;
                border-radius: 10px;
                overflow: hidden;
                transition: transform 0.2s;
            }}
            .card:hover {{
                transform: scale(1.02);
            }}
            img {{
                width: 100%;
                display: block;
            }}
            .info {{
                padding: 10px;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <h1>QC Mosaic Gallery</h1>
        <div class="grid">
            {"".join(rows_html)}
        </div>
    </body>
    </html>
    """

    output_html = Path(output_html)

    # Save inside mosaic dir so images resolve easily
    gallery_path = mosaic_dir / output_html.name

    with open(gallery_path, "w") as f:
        f.write(html_content)

    print(f"🖼️ Gallery saved to: {gallery_path}")


# -----------------------
# MAIN
# -----------------------


def find_masks(root_dir):
    root = Path(root_dir)
    return list(root.rglob("*T1w_mask.nii.gz"))
    # return sorted(str(p) for p in root.rglob("*T1w_mask.nii.gz"))


def create_curated_symlinks(df, source_root, curated_dir):
    source_root = Path(source_root).resolve()
    curated_dir = Path(curated_dir).resolve()
    curated_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------
    # BUILD PREFIXES TO EXCLUDE
    # -----------------------
    def get_prefix(mask_path):
        name = Path(mask_path).name
        return name.replace("_mask.nii.gz", "")

    outlier_prefixes = set(df[df["flag"] != "OK"]["mask"].apply(get_prefix))

    print(f"Excluding {len(outlier_prefixes)} acquisitions")
    print(f"Creating curated dataset with symlinks in {curated_dir}...")

    # -----------------------
    # WALK SOURCE TREE
    # -----------------------
    for root, _, files in os.walk(source_root):
        root_path = Path(root)

        # recreate directory
        rel_path = root_path.relative_to(source_root)
        dst_dir = curated_dir / rel_path
        dst_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            src_file = root_path / f
            dst_file = dst_dir / f

            # -----------------------
            # SKIP FILES MATCHING BAD PREFIX
            # -----------------------
            skip = False
            for prefix in outlier_prefixes:
                if f.startswith(prefix):
                    skip = True
                    break

            if skip:
                continue

            # -----------------------
            # CREATE SYMLINK
            # -----------------------
            try:
                if not dst_file.exists():
                    os.symlink(src_file.resolve(), dst_file)
            except Exception as e:
                print(f"⚠️ Symlink failed: {src_file} -> {e}")


def main(
    source_root,
    mni_mask_path,
    output_csv,
    threshold=0.92,
    curated_dir=None,
    make_mosaics=False,
):

    output_csv = Path(output_csv)
    output_html = output_csv.with_suffix(".html")

    # -----------------------
    # CHECK SAVE LOCATION FIRST
    # -----------------------
    try:
        output_csv.parent.mkdir(parents=True, exist_ok=True)

        test_file = output_csv.parent / ".write_test"
        with open(test_file, "w") as f:
            f.write("test")
        test_file.unlink()

    except Exception as e:
        raise RuntimeError(
            f"Cannot write to output directory: {output_csv.parent}\n{e}"
        )

    # -----------------------
    # HELPER: post-processing
    # -----------------------
    def postprocess(df):
        # recompute outliers (always)
        df = detect_outliers(df, threshold)

        # save updated CSV
        df.to_csv(output_csv, index=False)

        # plots
        plot_metrics(results=df.to_dict("records"), output_html=output_html)

        # mosaics (optional)
        if make_mosaics:
            mosaic_dir = output_csv.parent / output_csv.stem
            mosaic_dir.mkdir(parents=True, exist_ok=True)
            generate_outlier_mosaics(df=df, output_dir=mosaic_dir)

        # curated dataset (optional)
        if curated_dir is not None:
            create_curated_symlinks(df, source_root, curated_dir)

        return df

    # -----------------------
    # SKIP IF EXISTS
    # -----------------------
    if output_csv.exists() and output_html.exists():
        print("CSV + HTML already exist → skipping metric computation")

        df = pd.read_csv(output_csv)

        if df.empty:
            raise RuntimeError("Existing CSV is empty → cannot reuse.")

        df = postprocess(df)

        print("Done (reuse mode).")
        return

    # -----------------------
    # COMPUTE METRICS
    # -----------------------
    print("No existing CSV + HTML found → computing metrics from scratch")
    print(f"Results will be saved in {output_csv} and {output_html}")

    print("Loading MNI mask...")
    mni_mask, _ = load_nifti(mni_mask_path)

    print("Searching for masks...")
    mask_paths = find_masks(source_root)

    results = []

    for mask_path in tqdm(mask_paths):
        try:
            mask_path = str(mask_path)
            base = mask_path.replace("mask.nii.gz", "")
            # brain_path = base + "normalized.nii.gz"
            brain_path = base + "brain.nii.gz"  # more correct but no impact on metrics
            seg_path = base + "segm.nii.gz"

            # -----------------------
            # HANDLE MISSING FILES
            # -----------------------
            if not os.path.exists(brain_path) or not os.path.exists(seg_path):
                results.append(
                    {"mask": mask_path, "dice": np.nan, "flag": "MISSING_FILES"}
                )
                continue

            mask, _ = load_nifti(mask_path)
            brain, _ = load_nifti(brain_path)
            seg, _ = load_nifti(seg_path)

            if mask.shape != mni_mask.shape:
                results.append(
                    {"mask": mask_path, "dice": np.nan, "flag": "SHAPE_MISMATCH"}
                )
                continue

            # -----------------------
            # METRICS
            # -----------------------
            mask_bin = mask > 0
            mni_bin = mni_mask > 0
            dice = compute_dice(mask_bin, mni_bin)

            wm_vals = extract_region(brain, seg, WM_LABELS)
            gm_vals = extract_region(brain, seg, GM_LABELS)
            csf_vals = extract_region(brain, seg, CSF_LABELS)

            mu_wm, mu_gm, mu_csf = np.mean(wm_vals), np.mean(gm_vals), np.mean(csf_vals)
            sigma_wm, sigma_gm, sigma_csf = (
                np.std(wm_vals),
                np.std(gm_vals),
                np.std(csf_vals),
            )

            air_vals = brain[mask == 0]
            sigma_air = np.std(air_vals)

            n_wm = np.sum(np.isin(seg, WM_LABELS))
            n_gm = np.sum(np.isin(seg, GM_LABELS))
            n_csf = np.sum(np.isin(seg, CSF_LABELS))

            results.append(
                {
                    "mask": mask_path,
                    "dice": dice,
                    "snr_wm": snr(mu_wm, sigma_wm, n_wm),
                    "snr_gm": snr(mu_gm, sigma_gm, n_gm),
                    "snr_csf": snr(mu_csf, sigma_csf, n_csf),
                    "cnr": cnr(mu_wm, mu_gm, sigma_air, sigma_wm, sigma_gm),
                    "cjv": cjv(mu_wm, mu_gm, sigma_wm, sigma_gm),
                    "wm2max": wm2max(brain, mu_wm),
                    "wm_frac": np.sum(np.isin(seg, WM_LABELS)) / np.sum(seg > 0),
                    "gm_frac": np.sum(np.isin(seg, GM_LABELS)) / np.sum(seg > 0),
                    "csf_frac": np.sum(np.isin(seg, CSF_LABELS)) / np.sum(seg > 0),
                    "sigma_air": sigma_air,
                    "flag": None,
                }
            )

        except Exception as e:
            print(f"Error: {mask_path} -> {e}")
            results.append({"mask": mask_path, "dice": np.nan, "flag": "ERROR"})

    if len(results) == 0:
        raise RuntimeError("No valid results computed.")

    df = pd.DataFrame(results)

    # -----------------------
    # POSTPROCESS (shared)
    # -----------------------
    postprocess(df)

    print("Done.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", required=True, help="path of the root of the dataset"
    )
    parser.add_argument("--mni", required=True, help="MNI brain mask path")
    parser.add_argument("--csv_output", required=True, help="CSV full path with name")
    parser.add_argument(
        "--threshold", type=float, default=0.92, help="MNI dice threshold"
    )
    parser.add_argument(
        "--curated_dir",
        type=str,
        default=None,
        help="Directory to create symlinked curated dataset (non-outliers only)",
    )

    parser.add_argument(
        "--mosaics",
        default=False,
        help="Generate mosaic images (slower)",
    )

    args = parser.parse_args()

    main(
        source_root=args.source,
        mni_mask_path=args.mni,
        output_csv=args.csv_output,
        threshold=args.threshold,
        curated_dir=args.curated_dir,
        make_mosaics=args.mosaics,
    )
