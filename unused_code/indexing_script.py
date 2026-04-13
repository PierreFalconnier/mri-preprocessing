import json
import subprocess
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# %% INDEXING SCRIPT


root = Path("/run/media/falconnier/bb9ecfb7-b58f-41e9-a37d-fda12951eb4e/extracted/raw/")
csv_path = Path(
    "/home/falconnier/Documents/mri-preprocessing/csv_exploration/PPMI_explo/ppmi_clinical_imaging_merged_20260324_174815.csv"
)

df = pd.read_csv(csv_path, dtype=str)

df["Image ID"] = (
    df["Image ID"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
)

records = []

for subject_dir in tqdm(root.iterdir(), desc="Processing subjects"):
    if not subject_dir.is_dir():
        continue

    subject = subject_dir.name

    for seq_dir in subject_dir.iterdir():
        description = seq_dir.name

        for date_dir in seq_dir.iterdir():
            for image_dir in date_dir.iterdir():
                if image_dir.name.startswith("I"):
                    image_id = image_dir.name[1:]

                    print(f"Processing {subject} - {description} - {image_id}")

                    # match session
                    image_id = image_id.strip()
                    row = df[df["Image ID"] == image_id]

                    if len(row) == 0:
                        session = "unknown"
                    else:
                        session = row.iloc[0]["EVENT_ID"]

                    records.append(
                        {
                            "subject": subject,
                            "image_id": image_id,
                            "description": description,
                            "dicom_path": str(image_dir),
                            "session": session,
                        }
                    )

df_out = pd.DataFrame(records)
# df_out.to_csv("ppmi_index.csv", index=False)

# print("Saved ppmi_index.csv")

# %%

json_path = Path(
    "/home/falconnier/Documents/mri-preprocessing/csv_exploration/PPMI_explo/ppmi_imaging_descriptions.json"
)
bids_root = Path("/home/falconnier/Documents/mri-preprocessing/PPMI_BIDS")


# load JSON description map
with open(json_path, "r") as f:
    desc_map = json.load(f)


def map_to_bids(description):
    """
    Map raw description to BIDS datatype/suffix using JSON.
    Returns tuple (datatype, suffix) or None if unknown
    """
    description = description.strip()
    # anatomical
    for suffix, desc_list in desc_map.get("anat", {}).items():
        if description in desc_list:
            return "anat", suffix
    # diffusion
    for desc in desc_map.get("dwi", []):
        if description == desc:
            return "dwi", "dwi"
    # functional
    for desc in desc_map.get("func", []):
        if description == desc:
            return "func", "bold"
    # unknown
    return None, None


records = []

for subject_dir in tqdm(root.iterdir(), desc="Processing subjects"):
    if not subject_dir.is_dir():
        continue
    subject = subject_dir.name

    for seq_dir in subject_dir.iterdir():
        description = seq_dir.name

        for date_dir in seq_dir.iterdir():
            for image_dir in date_dir.iterdir():
                if image_dir.name.startswith("I"):
                    image_id = image_dir.name[1:]
                    row = df[df["Image ID"] == image_id]

                    session = row.iloc[0]["EVENT_ID"] if len(row) > 0 else "unknown"
                    bids_session = f"ses-{session}"

                    datatype, suffix = map_to_bids(description)
                    if datatype is None:
                        print(f"WARNING: Unknown mapping for {description}, skipping")
                        continue

                    # output directory
                    out_dir = bids_root / f"sub-{subject}" / bids_session / datatype
                    out_dir.mkdir(parents=True, exist_ok=True)

                    # convert DICOMs to NIfTI using dcm2niix
                    # dcm2niix -z y -f <filename> -o <outdir> <dicomdir>
                    fname_template = f"sub-{subject}_{bids_session}_run-01_{suffix}"
                    dicom_dir = str(image_dir)
                    subprocess.run(
                        [
                            "dcm2niix",
                            "-z",
                            "y",
                            "-f",
                            fname_template,
                            "-o",
                            str(out_dir),
                            dicom_dir,
                        ]
                    )

                    records.append(
                        {
                            "subject": subject,
                            "session": session,
                            "description": description,
                            "datatype": datatype,
                            "suffix": suffix,
                            "dicom_path": dicom_dir,
                            "bids_path": str(out_dir / (fname_template + ".nii.gz")),
                        }
                    )

df_bids = pd.DataFrame(records)
df_bids.to_csv("ppmi_bids_mapping.csv", index=False)
print("Saved ppmi_bids_mapping.csv")
