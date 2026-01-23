import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import nibabel as nib
import numpy as np
import pandas as pd
from tqdm import tqdm

# ----------------------------
# CONFIG
# ----------------------------
bids_dir = "/home/falconnier/Downloads/CamCAN"  # Path to BIDS root
output_csv = "t1w_iqm_results.csv"  # CSV output
max_workers = os.cpu_count()  # Use all available cores


# ----------------------------
# HELPER FUNCTION
# ----------------------------
def compute_iqm(sub):
    """
    Compute simple IQMs for one subject:
    - mean intensity
    - std intensity
    - brain mask: voxels > 0
    Returns (subject_id, dict)
    """
    try:
        img_path = os.path.join(bids_dir, sub, "anat", f"{sub}_T1w.nii.gz")
        img = nib.load(img_path)
        data = img.get_fdata(dtype=np.float32)
        mask = data > 0
        mean_intensity = data[mask].mean()
        std_intensity = data[mask].std()
        return sub, {"mean": mean_intensity, "std": std_intensity}
    except Exception as e:
        print(f"Error processing {sub}: {e}")
        return sub, {"mean": np.nan, "std": np.nan}


# ----------------------------
# GET SUBJECTS
# ----------------------------
subjects = [d for d in os.listdir(bids_dir) if d.startswith("sub-")]
print(f"Found {len(subjects)} subjects.")

# ----------------------------
# PARALLEL PROCESSING
# ----------------------------
iqm = {}

with ProcessPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(compute_iqm, sub): sub for sub in subjects}

    for future in tqdm(
        as_completed(futures), total=len(futures), desc="Computing IQMs"
    ):
        sub, metrics = future.result()
        iqm[sub] = metrics

# ----------------------------
# CREATE DATAFRAME
# ----------------------------
df = pd.DataFrame.from_dict(iqm, orient="index")
df.index.name = "subject"

# ----------------------------
# OUTLIER DETECTION (1.5 IQR)
# ----------------------------
q1, q3 = df["mean"].quantile([0.25, 0.75])
iqr = q3 - q1
lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr

df["outlier"] = (df["mean"] < lower) | (df["mean"] > upper)

print(f"Detected {df['outlier'].sum()} potential outliers out of {len(df)} subjects.")

# ----------------------------
# SAVE TO CSV
# ----------------------------
df.to_csv(output_csv)
print(f"IQM results saved to {output_csv}")
