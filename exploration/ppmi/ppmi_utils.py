import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def load_ppmi_csvs(base_dir, remove_date_suffix=True):
    data_dict = {}
    for csv_path in base_dir.rglob("*.csv"):
        if csv_path.exists():
            df = pd.read_csv(csv_path, low_memory=False)

            # Standardize columns
            df.columns = df.columns.str.strip().str.upper()

            # if "EVENT_ID" not in df.columns:
            #     print(
            #         f"Warning: 'EVENT_ID' column not found in {csv_path.name}. This file may not be visit-level."
            #     )
            # print(
            #     f"Loaded {csv_path.name} with columns EVENT ? {'EVENT_ID' in df.columns}"
            # )

            # Remove trailing date part from filename
            stem = csv_path.stem
            clean_name = stem.rsplit("_", 1)[0] if remove_date_suffix else stem

            data_dict[clean_name] = df
        else:
            print(f"Missing: {csv_path.name}")
    return data_dict


def build_visit_backbone(ppmi_data):
    visit_tables = []
    for name, df in ppmi_data.items():
        if set(["PATNO", "EVENT_ID"]).issubset(df.columns):
            visit_tables.append((name, df.copy()))

    if not visit_tables:
        raise ValueError("No visit-level tables found.")

    # Start with first visit-level table
    name, backbone = visit_tables[0]

    for name, df in visit_tables[1:]:
        backbone = backbone.merge(
            df, on=["PATNO", "EVENT_ID"], how="outer", suffixes=("", f"_{name}")
        )

    return backbone


def add_subject_level_tables(backbone, ppmi_data):

    for name, df in ppmi_data.items():
        # Only PATNO but no EVENT_ID
        if "PATNO" in df.columns and "EVENT_ID" not in df.columns:
            backbone = backbone.merge(
                df, on="PATNO", how="left", suffixes=("", f"_{name}")
            )

    return backbone


def merge_ppmi_tables(ppmi_data):
    backbone = build_visit_backbone(ppmi_data)
    master_df = add_subject_level_tables(backbone, ppmi_data)
    return master_df


def plot_bar(df, col, title=None, figsize=(6, 4), annotate=True):
    """
    Bar plot for categorical column with counts annotated on top.
    Includes missing values as 'Missing'.
    """
    if not title:
        title = f"Counts of {col}"

    counts = df[col].value_counts(dropna=False).sort_values(ascending=False)

    # Replace NaN index with "Missing"
    labels = counts.index.to_series().fillna("MISSING VALUES (NA)").astype(str)

    plt.figure(figsize=figsize)
    ax = sns.barplot(x=labels, y=counts.values, palette="viridis")

    plt.title(title)
    plt.xlabel(col)
    plt.ylabel("Count")
    plt.xticks(rotation=45, ha="right")

    if annotate:
        for i, v in enumerate(counts.values):
            if v > 0:
                ax.text(i, v + 0.5, str(v), ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.show()


def plot_hist(df, col, title=None):
    if not title:
        title = f"Distribution of {col}"
    plt.figure(figsize=(6, 4))

    # Plot histogram
    ax = sns.histplot(df[col], bins=30, kde=False)  # disable KDE for counts clarity

    plt.title(title)
    plt.xlabel(col)
    plt.ylabel("Count")

    # Annotate counts on top of each bin
    for patch in ax.patches:
        height = patch.get_height()
        if height > 0:  # only annotate non-empty bins
            ax.text(
                patch.get_x() + patch.get_width() / 2,  # center of bin
                height + 0.5,  # slightly above the bar
                int(height),  # show integer count
                ha="center",
                va="bottom",
                fontsize=8,
            )

    plt.show()


# from the Code_list but modified visits and remote to match the values
# of the csv from idaSearch
event_id_to_visit = {
    "AV1": "Unscheduled Telephone AV-133",
    "AV133": "AV-133",
    "AV133TC": "AV-133 Telephone Follow up",
    "AV2": "Unscheduled Telephone AV-133",
    "AV3": "Unscheduled Telephone AV-133",
    "AV4": "Unscheduled Telephone AV-133",
    "BL": "Baseline",
    "CONSENT": "Consent",
    "CTCCONLY": "CTCCONLY",
    "ED": "Event Driven",
    "FLORBET": "Florbetaben Imaging",
    "FLORBETC": "Florbetaben Telephone Call",
    "FNL": "Final Visit",
    "GMU": "Genetic Testing",
    "LOG": "Logs",
    "P102": "Phone Visit (Month 102)",
    "P114": "Phone Visit (Month 114)",
    "P126": "Phone Visit (Month 126)",
    "P138": "Phone Visit (Month 138)",
    "P150": "Phone Visit (Month 150)",
    "P78": "Phone Visit (Month 78)",
    "P90": "Phone Visit (Month 90)",
    "PW": "Premature Withdrawal",
    "PW1": "Premature Withdrawl -ND",
    "R01": "Remote Visit 01",
    "R04": "Remote Visit 04",
    "R06": "Remote Visit 06",
    "R08": "Remote Visit 08",
    "R10": "Remote Visit 10",
    "R12": "Remote Visit 12",
    "R13": "Remote Visit 13",
    "R14": "Remote Visit 14",
    "R15": "Remote Visit 15",
    "R16": "Remote Visit 16",
    "R17": "Remote Visit 17",
    "R18": "Remote Visit 18",
    "R19": "Remote Visit 19",
    "R20": "Remote Visit 20",
    "R21": "Remote Visit 21",
    "R22": "Remote Visit 22",
    "R23": "Remote Visit 23",
    "R24": "Remote Visit 24",
    "RANDOM": "Randomize",
    "RS1": "Re-Screen",
    "RS2": "Second Re-Screen",
    "SC": "Screening",
    "SC99": "Other Screening",
    "SCBL": "Screening/Baseline Combined",
    "SKINBIO": "Skin Biopsy",
    "SKINBITC": "Skin Biopsy Telephone Call",
    "ST": "Symptomatic Therapy",
    "STC": "Symptomatic Therapy Telephone Call",
    "T06": "Telephone Contact (Month 6)",
    "T108": "Telephone Contact",
    "T12": "Telephone Contact (Month 12)",
    "T132": "Telephone Contact",
    "T15": "Telephone Contact (Month 15)",
    "T156": "Telephone Contact",
    "T17": "Telephone Contact",
    "T18": "Telephone Contact (Month 18)",
    "T19": "Telephone Contact",
    "T21": "Telephone Contact (Month 21)",
    "T24": "Telephone Contact (Month 24)",
    "T27": "Telephone Contact (Month 27)",
    "T30": "Telephone Contact (Month 30)",
    "T33": "Telephone Contact (Month 33)",
    "T36": "Telephone Contact (Month 36)",
    "T39": "Telephone Contact (Month 39)",
    "T42": "Telephone Contact (Month 42)",
    "T45": "Telephone Contact (Month 45)",
    "T48": "Telephone Contact (Month 48)",
    "T51": "Telephone Contact (Month 51)",
    "T54": "Telephone Contact (Month 54)",
    "T57": "Telephone Contact (Month 57)",
    "T60": "Telephone Contact (Month 60)",
    "T72": "Telephone Contact (Month 72)",
    "T84": "Telephone Contact",
    "T96": "Telephone Contact (Month 96)",
    "TAPFNL": "TAP Final",
    "TBL": "Telephone Contact (BL)",
    "TDB": "Digital Biomarker Telephone Followup",
    "TPW": "Telephone Contact - PW",
    "TRANS": "Transition",
    "TSC": "Telephone Contact (SC)",
    "TST": "Telephone Contact - Symptomatic Therapy",
    "U01": "Unscheduled Visit 01",
    "U02": "Unscheduled Visit 02",
    "U03": "Unscheduled Visit 03",
    "U04": "Unscheduled Visit 04",
    "U05": "Unscheduled Visit 05",
    "U06": "Unscheduled Visit 06",
    "UP1": "Unscheduled Telephone Contact",
    "UP2": "Unscheduled Telephone Contact",
    "UP3": "Unscheduled Telephone Contact",
    "UT1": "Unscheduled Telephone Contact",
    "UT2": "Unscheduled Telephone Contact",
    "UT3": "Unscheduled Telephone Contact",
    "UT4": "Unscheduled Telephone Contact",
    "V01": "Month 3",
    "V02": "Month 6",
    "V03": "Month 9",
    "V04": "Month 12",
    "V05": "Month 18",
    "V06": "Month 24",
    "V07": "Month 30",
    "V08": "Month 36",
    "V09": "Month 42",
    "V10": "Month 48",
    "V11": "Month 54",
    "V12": "Month 60",
    "V13": "Month 72",
    "V14": "Month 84",
    "V15": "Month 96",
    "V16": "Month 108",
    "V17": "Month 120",
    "V18": "Month 132",
    "V19": "Month 144",
    "V20": "Month 156",
    "V21": "Month 168",
    "V22": "Month 180",
    "V23": "Month 192",
    "V24": "Month 204",
    "V25": "Month 216",
    "X01": "Transfer Event",
    "X02": "Transfer Event",
    "X03": "Transfer Event",
}

visit_to_event_id = {v: k for k, v in event_id_to_visit.items()}


fields = [
    "Acquisition Plane",
    "Slice Thickness",
    "Matrix Z",
    "Acquisition Type",
    "Manufacturer",
    "Mfg Model",
    "Field Strength",
    "Weighting",
]

numeric_fields = ["Slice Thickness", "Matrix Z", "Field Strength"]


# def parse_imaging_protocol(text):
#     if pd.isna(text):
#         return {}

#     items = text.split(";")
#     parsed = {}

#     for item in items:
#         if "=" in item:
#             key, value = item.split("=", 1)
#             parsed[key.strip()] = value.strip()

#     return parsed


def parse_imaging_protocol(text):
    """Parse 'key=value;...' text into a dictionary."""
    if pd.isna(text):
        return {}

    parsed = {}
    for item in text.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Try converting to numeric
            try:
                value_numeric = pd.to_numeric(value)
                parsed[key] = value_numeric
            except ValueError:
                parsed[key] = value
    return parsed


primdiag_map = {
    1: "Idiopathic PD",
    10: "Motor neuron disease with parkinsonism",
    11: "Multiple system atrophy",
    12: "Neuroleptic-induced parkinsonism",
    13: "Normal pressure hydrocephalus",
    14: "Progressive supranuclear palsy",
    15: "Psychogenic parkinsonism",
    16: "Vascular parkinsonism",
    17: "No PD nor other neurological disorder",
    18: "Spinocerebellar Ataxia (SCA)",
    2: "Alzheimer's disease",
    23: "Prodromal non-motor PD",
    24: "Prodromal motor PD",
    25: "Prodromal Synucleinopathy (e.g., RBD)",
    3: "Frontotemporal dementia",
    4: "Corticobasal syndrome",
    5: "Dementia with Lewy bodies",
    6: "Dopa-responsive dystonia",
    7: "Essential tremor",
    8: "Hemiparkinson/hemiatrophy syndrome",
    9: "Juvenile autosomal recessive parkinsonism",
    97: "Other neurological disorder(s)",
}

cohort_map = {
    1: "Parkinson's Disease",
    2: "Healthy Control",
    3: "SWEDD",
    4: "Prodromal",
    7: "Genetic Registry - PD",
    8: "Genetic Registry - Unaffected",
}


def visit_sort_key(visit):
    if pd.isna(visit):
        return np.inf  # put NaN at the end

    if visit == "Baseline":
        return 0

    if visit == "Symptomatic Therapy":
        return -1  # or choose where you want it

    # Extract month number
    match = re.search(r"Month (\d+)", visit)
    if match:
        return int(match.group(1))

    return np.inf
