# %% IMPORTS AND PATHS

import argparse
import os
import re
import shutil
import subprocess
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# -----------------------------
# GLOBALS
# -----------------------------

RE_NEUROMELANIN = r"([nN][mM])|([gG][rR][eE].*[mM][tT])"

# dwi directions
VALID_DIRS = ["AP", "PA", "LR", "RL"]
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


def process_image(task):
    image_dir, row_dict, bids_name = task

    sub = f"sub-{row_dict['PATNO']}"
    ses = f"ses-{row_dict['EVENT_ID']}"
    mod = row_dict["BIDS_Modality"]

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
        str(image_dir),
    ]

    # try:
    #     subprocess.run(cmd, check=True, capture_output=True, text=True)
    # except subprocess.CalledProcessError as e:
    #     print(f"Error converting {row_dict['Image ID']}: {e.stderr}")

    output_files = []

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )

        # Track expected outputs (adjust pattern if needed)
        output_files = list(Path(dest_dir).glob(f"{bids_name}*.nii*"))

        if not output_files:
            raise RuntimeError("No NIfTI files produced")

    except Exception as e:
        print(
            f"Error converting {row_dict['Image ID']} with the expected bids name {bids_name}: {e}"
        )

        # Remove potentially corrupted outputs
        for f in output_files:
            f.unlink(missing_ok=True)

        # Optionally remove directory if empty
        if Path(dest_dir).exists() and not any(Path(dest_dir).iterdir()):
            shutil.rmtree(dest_dir)

        raise  # re-raise if you want upstream handling


# %% MAIN


if __name__ == "__main__":
    # PARSE ARGUMENTS
    parser = argparse.ArgumentParser(
        description="Convert DICOM dataset to BIDS using dcm2niix"
    )

    parser.add_argument(
        "--root",
        type=Path,
        help="Root directory containing extracted DICOM data",
    )

    parser.add_argument(
        "--csv",
        dest="csv_path",
        type=Path,
        help="Path to CSV file with metadata",
    )

    parser.add_argument(
        "--bids-root",
        type=Path,
        help="Output BIDS root directory",
    )
    args = parser.parse_args()
    root = args.root
    csv_path = args.csv_path
    bids_root = args.bids_root

    RUN_COUNTERS = defaultdict(int)

    df = pd.read_csv(csv_path, dtype=str)

    df["Image ID"] = (
        df["Image ID"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )

    # -----------------------------
    # PHASE 1 — BUILD TASKS (SEQUENTIAL)
    # -----------------------------
    tasks = []

    for subject_dir in tqdm(root.iterdir(), desc="Scanning subjects"):
        if not subject_dir.is_dir():
            continue

        subject = subject_dir.name

        for seq_dir in subject_dir.iterdir():
            description = seq_dir.name

            for date_dir in seq_dir.iterdir():
                for image_dir in date_dir.iterdir():
                    if not image_dir.name.startswith("I"):
                        continue

                    image_id = image_dir.name[1:]
                    row = df[df["Image ID"] == image_id]

                    if len(row) == 0:
                        print(
                            f"No match in CSV for image ID {image_id} "
                            f"(subject {subject}, description {description})"
                        )
                        continue

                    row = row.iloc[0]
                    row_dict = row.to_dict()

                    # compute bids_name HERE (sequential : necessay for correct run numbering)
                    bids_name = build_bids_name(row)
                    if bids_name is None:
                        continue

                    tasks.append((image_dir, row_dict, bids_name))

    print(f"\nTotal tasks: {len(tasks)}")

    # -----------------------------
    # PHASE 2 — PARALLEL CONVERSION
    # -----------------------------
    max_workers = min(8, os.cpu_count())

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        list(tqdm(executor.map(process_image, tasks), total=len(tasks)))
