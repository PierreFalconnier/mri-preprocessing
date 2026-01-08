from pathlib import Path

import numpy as np
import pandas as pd

# ======= FUNCTIONS


def find_closest_diag(row, diag_df):
    # Get all diagnoses for this patient
    diags = diag_df[diag_df["subject_id"] == row["subject_id"]]
    # Remove rows with missing Age
    diags = diags.dropna(subset=["Age"])
    if diags.empty or pd.isna(row["Age"]):
        return np.nan
    # Find the diagnosis with the closest Age
    idx = (diags["Age"] - row["Age"]).abs().idxmin()
    closest_diag = diags.loc[idx]
    return closest_diag["NORMCOG"]


def t1w_exists(row):
    filename_pattern = row["subject_id"] + "_" + row["session_id"] + "*T1w.nii.gz"
    subject_folder = oasis3_data_dir / row["subject_id"]

    if not subject_folder.exists() or not subject_folder.is_dir():
        return False

    # Search recursively for matching files
    matches = list(subject_folder.rglob(filename_pattern))

    return len(matches) > 0


# ======= PATHS SETUP
root_dir = Path(__file__).parents[2]
data_dir = root_dir / "data"
oasis3_data_dir = data_dir / "OASIS3" / "raw"

sessions_csv_path = oasis3_data_dir.parent / "all_mr_sessions_full_with_age.csv"
diagnoses_csv_path = oasis3_data_dir.parent / "OASIS3_UDSd1_diagnoses.csv"

# ======= READ CSV FILES

sessions_df = pd.read_csv(sessions_csv_path)  # ID, MR SESSIONS, age
diagnoses_df = pd.read_csv(diagnoses_csv_path)  # ID, AGE, DIAGNOSTIC

sessions_df = sessions_df.rename(
    columns={
        "Subject": "subject_id",
        "MR ID": "session_id",
    }
)

diagnoses_df = diagnoses_df.rename(
    columns={
        "OASISID": "subject_id",
        "age at visit": "Age",
    }
)

# ========= FILTERING DATA
# get rid of sessions missing the age (25%),
# get the diagnostic corresponding to the closest age at visit
# remove sessions with no matching diagnosis
# get rid of sessions with no T1w scan
# Keep only rows where T1w exists (True)
sessions_df.dropna(subset=["Age"], inplace=True)
sessions_df["NORMCOG"] = sessions_df.apply(
    lambda row: find_closest_diag(row, diagnoses_df), axis=1
)
sessions_df.dropna(subset=["NORMCOG"], inplace=True)

# change str values to match the folders and files format
sessions_df["session_id"] = (
    "ses-" + sessions_df["session_id"].astype(str).str.split("_").str[-1]
)
sessions_df["subject_id"] = "sub-" + sessions_df["subject_id"]

# check if T1w exists
sessions_df["T1w_exists"] = sessions_df.apply(t1w_exists, axis=1)
sessions_df = sessions_df.loc[sessions_df["T1w_exists"]].copy()

# ========= SAVE THE CSV

print(sessions_df.head(3))
print(sessions_df["subject_id"].nunique())
print(sessions_df.shape)

# output_path = sessions_csv_path.parent / "mr_sessions_with_diag.csv"
# sessions_df.to_csv(output_path, index=False)
