# %% IMPORTS AND PATHS

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import pandas as pd
from tqdm import tqdm

json_path = Path(
    "/home/falconnier/Documents/mri-preprocessing/csv_exploration/PPMI_explo/ppmi_imaging_descriptions.json"
)
bids_root = Path(
    "/run/media/falconnier/bb9ecfb7-b58f-41e9-a37d-fda12951eb4e/test_PPMI_BIDS"
)
root = Path("/run/media/falconnier/bb9ecfb7-b58f-41e9-a37d-fda12951eb4e/extracted/raw/")
csv_path = Path(
    "/home/falconnier/Documents/mri-preprocessing/csv_exploration/PPMI_explo/ppmi_clinical_imaging_merged_20260324_174815.csv"
)

# %% CREATE INDEXING

df = pd.read_csv(csv_path, dtype=str)

df["Image ID"] = (
    df["Image ID"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
)

with open(json_path) as f:
    desc_map = json.load(f)


def normalize(s):
    return s.upper().replace("_", " ").strip()


def get_modality(description):
    desc = normalize(description)

    # DWI
    for d in desc_map.get("dwi", []):
        if normalize(d) in desc:
            return "dwi", None

    # FUNC
    for d in desc_map.get("func", []):
        if normalize(d) in desc:
            return "func", "rest"

    # ANAT
    for subtype, lst in desc_map.get("anat", {}).items():
        for d in lst:
            if normalize(d) in desc:
                return "anat", subtype

    return "unknown", None


records = []

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

                image_id = image_dir.name[1:]  # remove the "I" prefix to match the CSV

                row = df[df["Image ID"] == image_id]
                session = row.iloc[0]["EVENT_ID"] if len(row) else "unknown"

                modality, subtype = get_modality(description)

                records.append(
                    {
                        "subject": subject,
                        "image_id": image_id,
                        "session": session,  # inferred from CSV using Image ID
                        "description": description,  # description from folder name
                        "dicom_path": str(image_dir),
                        "modality": modality,  # anat, func, dwi, or unknown
                        "subtype": subtype,  # for anat: t1w, t2w, etc.
                    }
                )

df_out = pd.DataFrame(records)

# %% SCRIPT TO INFER THE BIDS FILENAME COMPONENTS AND RUN CONVERSION


# -----------------------------
# GLOBALS
# -----------------------------


RE_NEUROMELANIN = r"([nN][mM])|([gG][rR][eE].*[mM][tT])"

# VALID_DIRS = ["AP", "PA", "LR", "RL"]

# DIR_RE_MAP = {
#     dir: f"[ \\-_]{dir[0]}[ \\-_>]*{dir[1]}(?:[ \\-_]|\\Z)" for dir in VALID_DIRS
# }

# DIR_DESCRIPTIONS_MAP = {
#     "LR": [
#         "2D DTI EPI FAT SHIFT LEFT",
#         "AX DTI 32 DIR FAT SHIFT L",
#         "AX DTI 32 DIR FAT SHIFT L NO ANGLE",
#         "AX DTI _reverse",
#     ],
#     "RL": [
#         "2D DTI EPI FAT SHIFT RIGHT",
#         "AX DTI 32 DIR FAT SHIFT R",
#         "AX DTI 32 DIR FAT SHIFT R NO ANGLE",
#     ],
# }

# DESCRIPTION_ACQ_MAP = {
#     "DTI_B0_PA": "B0",
#     "DTI_revB0_AP": "B0",
#     "DTI_B700_64dir_PA": "B700",
#     "DTI_B1000_64dir_PA": "B1000",
#     "DTI_B2000_64dir_PA": "B2000",
# }


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
RUN_COUNTERS = defaultdict(int)


def build_bids_name(row, df_imaging=None):
    sub = f"sub-{row['subject']}"
    ses = f"ses-{row['session']}"
    mod = row["modality"]
    desc = row["description"]
    image_id = row["image_id"]

    # -------------------------
    # ANAT
    # -------------------------
    if mod == "anat":
        suffix = row["subtype"]

        # --- neuromelanin special case
        if re.search(RE_NEUROMELANIN, desc):
            acq = TAG_NEUROMELANIN
            key = (sub, ses, mod, suffix, acq)

            RUN_COUNTERS[key] += 1
            run = RUN_COUNTERS[key]

            return f"{sub}_{ses}_acq-{acq}_run-{run:02d}_{suffix}"

        # --- normal anat
        plane, dims = infer_plane_dims(desc, protocol_dict)

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


def run_conversion(df, bids_root):
    # Create the BIDS root if it doesn't exist
    bids_root.mkdir(parents=True, exist_ok=True)

    print(f"Starting conversion of {len(df)} series...")

    for _, row in tqdm(df.iterrows(), total=len(df)):
        # 1. Skip unknown modalities
        if row["modality"] == "unknown":
            continue

        # 2. Build BIDS components
        sub = f"sub-{row['subject']}"
        ses = f"ses-{row['session']}"
        mod = row["modality"]

        # 3. Create destination directory
        dest_dir = bids_root / sub / ses / mod
        dest_dir.mkdir(parents=True, exist_ok=True)

        # 4. Construct BIDS filename (without extension)
        # We add the image_id to the filename to ensure uniqueness
        bids_name = build_bids_name(row)
        if bids_name is None:
            continue

        # 5. Run dcm2niix
        # -z y: compress to .nii.gz
        # -f: filename format
        # -o: output directory
        cmd = [
            "dcm2niix",
            "-z",
            "y",
            "-f",
            bids_name,
            "-o",
            str(dest_dir),
            row["dicom_path"],
        ]

        # Execute and catch errors
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"Error converting {row['image_id']}: {e.stderr}")


# Run it
run_conversion(df_out, bids_root)
