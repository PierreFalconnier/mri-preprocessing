import pandas as pd

# Set working directory (optional if running in same folder)
# import os
# os.chdir(r"C:\PPMI")

# Load CSV files
participant_status = pd.read_csv(
    "/home/falconnier/Documents/PPMI_study_data_starting_point/Participant_Status_12Feb2026.csv"
)
demographics = pd.read_csv(
    "/home/falconnier/Documents/PPMI_study_data_starting_point/Demographics_12Feb2026.csv"
)
codes = pd.read_csv(
    "/home/falconnier/Documents/PPMI_study_data_starting_point/Code_List_-__Annotated__12Feb2026.csv"
)
pd_diagnosis_history = pd.read_csv(
    "/home/falconnier/Documents/PPMI_study_data_starting_point/PD_Diagnosis_History_12Feb2026.csv"
)

# -----------------------------
# Create Genetic Subgroup
# -----------------------------

genetic_cols = [
    "ENRLPINK1",
    "ENRLPRKN",
    "ENRLSRDC",
    "ENRLHPSM",
    "ENRLRBD",
    "ENRLLRRK2",
    "ENRLSNCA",
    "ENRLGBA",
]


def determine_genetic_subgroup(row):
    total = sum([row[col] for col in genetic_cols if col in row])
    if total > 1:
        return "Multiple factors"
    elif row.get("ENRLPINK1", 0) == 1:
        return "PINK1"
    elif row.get("ENRLPRKN", 0) == 1:
        return "PARKIN"
    elif row.get("ENRLSRDC", 0) == 1:
        return "SRDC"
    elif row.get("ENRLHPSM", 0) == 1:
        return "HPSM"
    elif row.get("ENRLRBD", 0) == 1:
        return "RBD"
    elif row.get("ENRLLRRK2", 0) == 1:
        return "LRRK2"
    elif row.get("ENRLSNCA", 0) == 1:
        return "SNCA"
    elif row.get("ENRLGBA", 0) == 1:
        return "GBA"
    else:
        return ""


participant_status["GENETIC_SUBGROUP"] = participant_status.apply(
    determine_genetic_subgroup, axis=1
)

# -----------------------------
# Decode SEX and HANDED
# -----------------------------

sex_codes = codes[codes["ITM_NAME"] == "SEX"][["CODE", "DECODE"]].assign(
    CODE=lambda x: pd.to_numeric(x["CODE"], errors="coerce")
)

handed_codes = codes[codes["ITM_NAME"] == "HANDED"][["CODE", "DECODE"]].assign(
    CODE=lambda x: pd.to_numeric(x["CODE"], errors="coerce")
)

# -----------------------------
# Earliest PD Diagnosis Date
# -----------------------------

pd_diagnosis_history["PD_Diagnosis_Date"] = pd.to_datetime(
    "01/" + pd_diagnosis_history["PDDXDT"].astype(str),
    format="%d/%m/%Y",
    errors="coerce",
)

pd_dx_earliest = pd_diagnosis_history.groupby("PATNO", as_index=False)[
    "PD_Diagnosis_Date"
].min()

# -----------------------------
# Merge Everything
# -----------------------------

participant_master = (
    participant_status.merge(demographics, on="PATNO", how="left")
    .merge(sex_codes, left_on="SEX", right_on="CODE", how="left")
    .rename(columns={"DECODE": "SEX_DECODE"})
    .merge(
        handed_codes,
        left_on="HANDED",
        right_on="CODE",
        how="left",
        suffixes=("", "_HANDED"),
    )
    .rename(columns={"DECODE": "HANDED_DECODE"})
    .merge(pd_dx_earliest, on="PATNO", how="left")
)

# -----------------------------
# Fix Date Formats
# -----------------------------

participant_master["BIRTHDT"] = pd.to_datetime(
    "01/" + participant_master["BIRTHDT"].astype(str),
    format="%d/%m/%Y",
    errors="coerce",
)

participant_master["ENROLL_DATE"] = pd.to_datetime(
    "01/" + participant_master["ENROLL_DATE"].astype(str),
    format="%d/%m/%Y",
    errors="coerce",
)

# -----------------------------
# Select Final Columns
# -----------------------------

participant_master = participant_master[
    [
        "PATNO",
        "BIRTHDT",
        "COHORT_DEFINITION",
        "GENETIC_SUBGROUP",
        "ENROLL_AGE",
        "ENROLL_DATE",
        "ENROLL_STATUS",
        "SEX_DECODE",
        "HANDED_DECODE",
        "PD_Diagnosis_Date",
    ]
].sort_values("PATNO")

# -----------------------------
# Export to CSV
# -----------------------------

# participant_master.to_csv("Participant_Master_Merged.csv", index=False)
# print("Merged CSV saved as Participant_Master_Merged.csv")
