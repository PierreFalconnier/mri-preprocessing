import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def load_ppmi_csvs(base_dir, remove_date_suffix=True):
    data_dict = {}

    for csv_path in base_dir.rglob("*.csv"):
        if csv_path.exists():
            df = pd.read_csv(csv_path, low_memory=False)

            # Standardize columns
            df.columns = df.columns.str.strip().str.upper()

            # Remove trailing date part from filename
            stem = csv_path.stem
            clean_name = stem.rsplit("_", 1)[0] if remove_date_suffix else stem

            data_dict[clean_name] = df
        else:
            print(f"Missing: {csv_path.name}")

    return data_dict


def build_visit_backbone(ppmi_data, exclude_keys=("idaSearch",)):

    visit_tables = []

    for name, df in ppmi_data.items():
        if name in exclude_keys:
            continue

        if set(["PATNO", "EVENT_ID"]).issubset(df.columns):
            visit_tables.append((name, df.copy()))

    if not visit_tables:
        raise ValueError("No visit-level tables found.")

    # Start with first visit-level table
    name, backbone = visit_tables[0]
    # print(f"Backbone: {name} | {backbone.shape}")

    for name, df in visit_tables[1:]:
        backbone = backbone.merge(
            df, on=["PATNO", "EVENT_ID"], how="outer", suffixes=("", f"_{name}")
        )
        # print(f"Merged visit table: {name} | Shape: {backbone.shape}")

    return backbone


def add_subject_level_tables(backbone, ppmi_data, exclude_keys=("idaSearch",)):

    for name, df in ppmi_data.items():
        if name in exclude_keys:
            continue

        # Only PATNO but no EVENT_ID
        if "PATNO" in df.columns and "EVENT_ID" not in df.columns:
            backbone = backbone.merge(
                df, on="PATNO", how="left", suffixes=("", f"_{name}")
            )
            # print(f"Added subject table: {name} | Shape: {backbone.shape}")

    return backbone


def merge_ppmi_tables(ppmi_data, exclude_keys=("idaSearch",)):

    backbone = build_visit_backbone(ppmi_data, exclude_keys=exclude_keys)
    master_df = add_subject_level_tables(backbone, ppmi_data, exclude_keys=exclude_keys)

    return master_df


def plot_hist(df, col):
    plt.figure(figsize=(6, 4))

    # Plot histogram
    ax = sns.histplot(
        df[col].dropna(), bins=30, kde=False
    )  # disable KDE for counts clarity

    plt.title(f"Histogram of {col}")
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
