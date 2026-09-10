"""PPMI dataset adapter: BIDS naming, raw tree walking, and CSV loading.

Consolidated from the legacy ``PPMI_to_bids/ppmi_to_bids.py`` and
``csv_exploration/PPMI_explo/ppmi_utils.py``. This is the *only* module that
should contain PPMI-specific knowledge (folder layout, visit-code
vocabulary, diagnosis codebooks); everything else in the pipeline is generic.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

_RESOURCES_DIR = Path(__file__).parent
_DESCRIPTION_CATEGORIES_PATH = _RESOURCES_DIR / "ppmi_description_categories.json"
_IGNORED_DESCRIPTIONS_PATH = _RESOURCES_DIR / "ppmi_ignored_descriptions.csv"

# -----------------------------------------------------------------------
# BIDS naming
# -----------------------------------------------------------------------

RE_NEUROMELANIN = r"([nN][mM])|([gG][rR][eE].*[mM][tT])"

VALID_DWI_DIRS = ["AP", "PA", "LR", "RL"]
DWI_DIR_RE_MAP = {
    d: rf"[ \-_]{d[0]}[ \-_>]*{d[1]}(?:[ \-_]|\Z)" for d in VALID_DWI_DIRS
}
# descriptions not caught by the regex above
DWI_DIR_DESCRIPTIONS_MAP = {
    "LR": [
        "2D DTI EPI FAT SHIFT LEFT",
        "AX DTI 32 DIR FAT SHIFT L",
        "AX DTI 32 DIR FAT SHIFT L NO ANGLE",
        "AX DTI _reverse",
    ],
    "RL": [
        "2D DTI EPI FAT SHIFT RIGHT",
        "AX DTI 32 DIR FAT SHIFT R",
        "AX DTI 32 DIR FAT SHIFT R NO ANGLE",
    ],
}
DWI_DESCRIPTION_ACQ_MAP = {
    "DTI_B0_PA": "B0",
    "DTI_revB0_AP": "B0",
    "DTI_B700_64dir_PA": "B700",
    "DTI_B1000_64dir_PA": "B1000",
    "DTI_B2000_64dir_PA": "B2000",
}


def infer_dwi_dir(description: str) -> str | None:
    for direction, descriptions in DWI_DIR_DESCRIPTIONS_MAP.items():
        if description in descriptions:
            return direction
    for direction, regex in DWI_DIR_RE_MAP.items():
        if re.search(regex, description):
            return direction
    return None


def infer_dwi_acq(description: str) -> str | None:
    return DWI_DESCRIPTION_ACQ_MAP.get(description)


# -----------------------------------------------------------------------
# Description -> category classification
# -----------------------------------------------------------------------
#
# PPMI's own `Modality`/`Description` columns on ida.loni cannot be trusted
# for BIDS classification: `Modality` collapses everything to "MRI" (a raw
# T1w and a derived DTI-FA map both come back as MRI), and `Description` is
# free text entered per site/scanner/year, so the same acquisition shows up
# under dozens of spellings while unrelated things (localizers, calibration
# scans, DTI-derived ADC/FA/TRACEW maps) show up mixed in with usable scans.
# `ppmi_description_categories.json` and `ppmi_ignored_descriptions.csv` are
# a hand-curated mapping from the actual PPMI Description vocabulary to a
# trustworthy category, built by manually reviewing `mri-prep ida sequences`
# output; extend them (not the classification logic here) as new
# Descriptions turn up in fresh search exports.


@lru_cache(maxsize=1)
def _description_categories() -> dict[str, str]:
    """{Description: category}, category one of 'dwi', 'func', or
    'anat/<suffix>' (e.g. 'anat/T1w', 'anat/FLAIR')."""
    raw = json.loads(_DESCRIPTION_CATEGORIES_PATH.read_text())
    mapping: dict[str, str] = {}
    for description in raw.get("dwi", []):
        mapping[description] = "dwi"
    for description in raw.get("func", []):
        mapping[description] = "func"
    for suffix, descriptions in raw.get("anat", {}).items():
        for description in descriptions:
            mapping[description] = f"anat/{suffix}"
    return mapping


@lru_cache(maxsize=1)
def _ignored_descriptions() -> frozenset[str]:
    """Descriptions that are not a usable acquisition at all (localizers,
    scanner calibration, derived ADC/FA/TRACEW maps, ...) and should be
    dropped rather than classified."""
    with _IGNORED_DESCRIPTIONS_PATH.open(newline="") as f:
        return frozenset(
            row["Description"].strip()
            for row in csv.DictReader(f)
            if row["Description"].strip()
        )


def classify_description(description: str) -> str | None:
    """Map a raw ida.loni `Description` to a curated category, or None if it
    should be excluded (in `ppmi_ignored_descriptions.csv`) or is not yet
    covered by `ppmi_description_categories.json`.

    Callers cannot tell "ignored" apart from "not yet curated" from this
    return value alone; use `is_ignored_description` first if that
    distinction matters (e.g. to report new/unmapped Descriptions instead of
    silently treating them as ignored).
    """
    if not isinstance(description, str):
        return None
    description = description.strip()
    if description in _ignored_descriptions():
        return None
    return _description_categories().get(description)


def is_ignored_description(description: str) -> bool:
    return isinstance(description, str) and description.strip() in _ignored_descriptions()


def reload_description_resources() -> None:
    """Clear the cached Description->category/ignored mappings.

    `_description_categories`/`_ignored_descriptions` are read once and
    cached, so edits made to `ppmi_description_categories.json` /
    `ppmi_ignored_descriptions.csv` mid-session (e.g. while curating new
    Descriptions in a notebook) are invisible until this is called -- or the
    kernel is restarted.
    """
    _description_categories.cache_clear()
    _ignored_descriptions.cache_clear()


def split_category(category: str | None) -> tuple[str | None, str | None]:
    """Split a curated `category` ("dwi", "func", "anat/T1w", ...) into the
    (BIDS_Modality, Advanced_Modality) columns `PPMIAdapter.build_bids_name`
    and `mri_prep.bids.convert` expect: `BIDS_Modality` is the top-level
    modality the BIDS tree is grouped by; `Advanced_Modality` is the anat
    suffix (e.g. "T1w"), only meaningful when `BIDS_Modality == "anat"`."""
    if not isinstance(category, str):
        return None, None
    if category.startswith("anat/"):
        return "anat", category.removeprefix("anat/")
    return category, None


def annotate_categories(df: pd.DataFrame, description_col: str = "Description") -> pd.DataFrame:
    """Add `category`/`ignored` columns (see `classify_description`) plus the
    `BIDS_Modality`/`Advanced_Modality` split (see `split_category`) to a
    search-export DataFrame, without dropping any rows -- rows where
    `category` is null and `ignored` is False are Descriptions not yet
    covered by the curated mapping, worth reviewing and adding."""
    df = df.copy()
    df["ignored"] = df[description_col].map(is_ignored_description)
    df["category"] = df[description_col].map(classify_description)
    split = df["category"].map(split_category)
    df["BIDS_Modality"] = split.map(lambda t: t[0])
    df["Advanced_Modality"] = split.map(lambda t: t[1])
    return df


class PPMIAdapter:
    """Stateful adapter: keeps per-(sub, ses, ...) run counters so repeated
    acquisitions get run-01, run-02, ... consistently within one conversion
    pass."""

    def __init__(self) -> None:
        self._run_counters: dict[tuple, int] = defaultdict(int)

    def build_bids_name(self, row: pd.Series) -> str | None:
        sub = f"sub-{row['PATNO']}"
        ses = f"ses-{row['EVENT_ID']}"
        mod = row["BIDS_Modality"]
        desc = row["Description"]

        if mod == "anat":
            suffix = row["Advanced_Modality"]

            if re.search(RE_NEUROMELANIN, desc):
                key = (sub, ses, mod, suffix, "NM")
                run = self._next_run(key)
                return f"{sub}_{ses}_acq-NM_run-{run:02d}"

            plane = row.get("Acquisition Plane")
            dims = row.get("Acquisition Type")
            if plane and dims:
                acq = f"{plane}{dims}"
                key = (sub, ses, mod, suffix, acq)
                run = self._next_run(key)
                return f"{sub}_{ses}_acq-{acq}_run-{run:02d}_{suffix}"

            key = (sub, ses, mod, suffix)
            run = self._next_run(key)
            return f"{sub}_{ses}_run-{run:02d}_{suffix}"

        if mod == "dwi":
            suffix = "dwi"
            acq = infer_dwi_acq(desc)
            direction = infer_dwi_dir(desc)
            acq_str = f"_acq-{acq}" if acq else ""
            dir_str = f"_dir-{direction}" if direction else ""
            key = (sub, ses, mod, suffix, acq, direction)
            run = self._next_run(key)
            return f"{sub}_{ses}{acq_str}{dir_str}_run-{run:02d}_{suffix}"

        if mod == "func":
            suffix, task = "bold", "rest"
            key = (sub, ses, mod, task)
            run = self._next_run(key)
            return f"{sub}_{ses}_task-{task}_run-{run:02d}_{suffix}"

        return None

    def _next_run(self, key: tuple) -> int:
        self._run_counters[key] += 1
        return self._run_counters[key]

    def iter_source_images(self, raw_root: Path) -> Iterator[tuple[str, Path]]:
        """Walk sub-*/sequence/session/I<image_id>/ and yield (image_id, dir)."""
        for subject_dir in Path(raw_root).iterdir():
            if not subject_dir.is_dir():
                continue
            for seq_dir in subject_dir.iterdir():
                if not seq_dir.is_dir():
                    continue
                for date_dir in seq_dir.iterdir():
                    if not date_dir.is_dir():
                        continue
                    for image_dir in date_dir.iterdir():
                        if not image_dir.name.startswith("I"):
                            continue
                        yield image_dir.name[1:], image_dir

    def load_tabular(self, csv_root: Path) -> dict[str, pd.DataFrame]:
        from mri_prep.tabular.io import load_dataset_csvs

        return load_dataset_csvs(csv_root)

    def annotate_categories(self, df: pd.DataFrame, description_col: str = "Description") -> pd.DataFrame:
        """See module-level `annotate_categories` -- exposed on the adapter so
        generic callers (e.g. the CLI) can apply PPMI's curated Description
        classification without importing PPMI-specific names directly."""
        return annotate_categories(df, description_col=description_col)


# -----------------------------------------------------------------------
# Visit / diagnosis vocabularies (used by mri_prep.tabular for PPMI)
# -----------------------------------------------------------------------

EVENT_ID_TO_VISIT = {
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
VISIT_TO_EVENT_ID = {v: k for k, v in EVENT_ID_TO_VISIT.items()}

PRIMDIAG_MAP = {
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

COHORT_MAP = {
    1: "Parkinson's Disease",
    2: "Healthy Control",
    3: "SWEDD",
    4: "Prodromal",
    7: "Genetic Registry - PD",
    8: "Genetic Registry - Unaffected",
}


def parse_imaging_protocol(text: str) -> dict:
    """Parse the idaSearch 'key=value;...' Imaging Protocol column."""
    if pd.isna(text):
        return {}
    parsed: dict = {}
    for item in text.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key, value = key.strip(), value.strip()
        try:
            parsed[key] = pd.to_numeric(value)
        except ValueError:
            parsed[key] = value
    return parsed


def visit_sort_key(visit: str) -> float:
    """Sort key so visits order chronologically (Baseline first, then months)."""
    if pd.isna(visit):
        return np.inf
    if visit == "Baseline":
        return 0
    if visit == "Symptomatic Therapy":
        return -1
    match = re.search(r"Month (\d+)", visit)
    if match:
        return int(match.group(1))
    return np.inf
