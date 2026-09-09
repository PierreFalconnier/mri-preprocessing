# %% IMPORTS AND PATHS

import re
import subprocess
from collections import defaultdict
from pathlib import Path

import pandas as pd
from tqdm import tqdm

root = Path("/run/media/falconnier/bb9ecfb7-b58f-41e9-a37d-fda12951eb4e/extracted/raw/")
csv_path = Path(
    "/home/falconnier/Documents/mri-preprocessing/csv_exploration/PPMI_explo/ppmi_clinical_imaging_merged_20260325_155504.csv"
)

bids_root = Path(
    "/run/media/falconnier/bb9ecfb7-b58f-41e9-a37d-fda12951eb4e/test_PPMI_BIDS"
)

# -----------------------------
# GLOBALS
# -----------------------------


RE_NEUROMELANIN = r"([nN][mM])|([gG][rR][eE].*[mM][tT])"

# dwi directions
VALID_DIRS = ["AP", "PA", "LR", "RL"]
# DIR_RE_MAP = {
#     # will catch: ' R L', '_RL', 'R-L', 'R > L', etc.
#     dir: f"[ \-_]{dir[0]}[ \-_>]*{dir[1]}(?:[ \-_]|\Z)"
#     for dir in VALID_DIRS
# }
DIR_RE_MAP = {
    dir: rf"[ \-_]{dir[0]}[ \-_>]*{dir[1]}(?:[ \-_]|\Z)" for dir in VALID_DIRS
}

# for descriptions not handled by the above regex
DIR_DESCRIPTIONS_MAP = {
    "LR": [
        "2D DTI EPI FAT SHIFT LEFT",
        "AX DTI 32 DIR FAT SHIFT L",
        "AX DTI 32 DIR FAT SHIFT L NO ANGLE",
        "AX DTI _reverse",  # one subject has this and 'AX DTI _RL'
    ],
    "RL": [
        "2D DTI EPI FAT SHIFT RIGHT",
        "AX DTI 32 DIR FAT SHIFT R",
        "AX DTI 32 DIR FAT SHIFT R NO ANGLE",
    ],
}

# dwi acquisitions (for AP/PA scans)
DESCRIPTION_ACQ_MAP = {
    "DTI_B0_PA": "B0",
    "DTI_revB0_AP": "B0",
    "DTI_B700_64dir_PA": "B700",
    "DTI_B1000_64dir_PA": "B1000",
    "DTI_B2000_64dir_PA": "B2000",
}


def infer_dwi_dir(description):
    # 1. hardcoded descriptions
    for dir, descriptions in DIR_DESCRIPTIONS_MAP.items():
        if description in descriptions:
            return dir
    # 2. regex
    for dir, regex in DIR_RE_MAP.items():
        if re.search(regex, description):
            return dir
    return None


def infer_dwi_acq(description):
    return DESCRIPTION_ACQ_MAP.get(description)


# -----------------------------
# MAIN FUNCTION
# -----------------------------


def build_bids_name(row):

    sub = f"sub-{row['PATNO']}"
    ses = f"ses-{row['EVENT_ID']}"
    mod = row["BIDS_Modality"]
    desc = row["Description"]

    # -------------------------
    # ANAT
    # -------------------------
    if mod == "anat":
        suffix = row["Advanced_Modality"]

        # --- neuromelanin special case
        if re.search(RE_NEUROMELANIN, desc):
            acq = "NM"
            key = (sub, ses, mod, suffix, acq)

            RUN_COUNTERS[key] += 1
            run = RUN_COUNTERS[key]

            # return f"{sub}_{ses}_acq-{acq}_run-{run:02d}_{suffix}"
            return f"{sub}_{ses}_acq-{acq}_run-{run:02d}"

        # --- normal anat
        plane = row["Acquisition Plane"]
        dims = row["Acquisition Type"]

        if plane and dims:
            acq = f"{plane}{dims}"
            key = (sub, ses, mod, suffix, acq)

            RUN_COUNTERS[key] += 1
            run = RUN_COUNTERS[key]

            return f"{sub}_{ses}_acq-{acq}_run-{run:02d}_{suffix}"

        else:
            key = (sub, ses, mod, suffix)

            RUN_COUNTERS[key] += 1
            run = RUN_COUNTERS[key]

            return f"{sub}_{ses}_run-{run:02d}_{suffix}"

    # -------------------------
    # DWI
    # -------------------------
    elif mod == "dwi":
        suffix = "dwi"

        acq = infer_dwi_acq(desc)
        direction = infer_dwi_dir(desc)

        acq_str = f"_acq-{acq}" if acq else ""
        dir_str = f"_dir-{direction}" if direction else ""

        key = (sub, ses, mod, suffix, acq, direction)

        RUN_COUNTERS[key] += 1
        run = RUN_COUNTERS[key]

        return f"{sub}_{ses}{acq_str}{dir_str}_run-{run:02d}_{suffix}"

    # -------------------------
    # FUNC
    # -------------------------
    elif mod == "func":
        suffix = "bold"
        task = "rest"

        key = (sub, ses, mod, task)

        RUN_COUNTERS[key] += 1
        run = RUN_COUNTERS[key]

        return f"{sub}_{ses}_task-{task}_run-{run:02d}_{suffix}"

    return None


# %% CREATE INDEXING

if __name__ == "__main__":
    RUN_COUNTERS = defaultdict(int)

    df = pd.read_csv(csv_path, dtype=str)

    df["Image ID"] = (
        df["Image ID"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )

    for subject_dir in tqdm(root.iterdir()):
        if not subject_dir.is_dir():
            continue

        subject = subject_dir.name

        for seq_dir in subject_dir.iterdir():
            description = seq_dir.name

            for date_dir in seq_dir.iterdir():
                for image_dir in date_dir.iterdir():
                    if not image_dir.name.startswith("I"):
                        continue

                    # get image id and match to CSV
                    # remove the "I" prefix to match the CSV
                    image_id = image_dir.name[1:]
                    row = df[df["Image ID"] == image_id]
                    if len(row) == 0:
                        print(
                            f"No match in CSV for image ID {image_id} (subject {subject}, description {description})"
                        )
                        continue  # skip if no match in CSV

                    # get the bids name
                    row = row.iloc[0]
                    bids_name = build_bids_name(row)
                    if bids_name is None:
                        continue

                    # 5. Run dcm2niix
                    # -z y: compress to .nii.gz
                    # -f: filename format
                    # -o: output directory

                    sub = f"sub-{row['PATNO']}"
                    ses = f"ses-{row['EVENT_ID']}"
                    mod = row["BIDS_Modality"]

                    dest_dir = bids_root / sub / ses / mod
                    dest_dir.mkdir(parents=True, exist_ok=True)

                    cmd = [
                        "dcm2niix",
                        "-z",
                        "y",
                        "-f",
                        bids_name,
                        "-o",
                        str(dest_dir),
                        image_dir,
                    ]

                    # Execute and catch errors
                    try:
                        subprocess.run(cmd, check=True, capture_output=True, text=True)
                    except subprocess.CalledProcessError as e:
                        print(f"Error converting {row['Image ID']}: {e.stderr}")
