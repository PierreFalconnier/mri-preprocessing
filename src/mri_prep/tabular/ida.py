"""Reader and query helpers for ida.loni Advanced Image Search exports.

The Advanced Search CSV has the same shape for every study hosted on
ida.loni.usc.edu (PPMI, ADNI, AIBL, ...): one row per image, with subject and
visit columns, a free-text `Description` naming the acquisition, an `Image ID`,
and a semicolon-separated `Imaging Protocol` string holding the scanner
parameters. Which columns are present depends on the "display in result"
boxes ticked on the search page, so nothing here assumes a fixed column set --
core columns are used when available and everything else is passed through.

Typical use, from an exploration notebook:

    from mri_prep.tabular.ida import load_ida_search, describe_sequences

    df = load_ida_search("data/ADNI/csv/idaSearch_2026.csv")
    describe_sequences(df)          # which acquisitions exist, and how many
    df[df["Description"].str.contains("MPRAGE")]["Image ID"]  # -> your selection
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Columns the search page emits under stable names. Any of them may be absent
# depending on which "display in result" checkboxes were ticked.
SUBJECT_COL = "Subject ID"
VISIT_COL = "Visit"
DATE_COL = "Study Date"
MODALITY_COL = "Modality"
DESCRIPTION_COL = "Description"
IMAGE_ID_COL = "Image ID"
PROTOCOL_COL = "Imaging Protocol"
# "Original" (raw scanner DICOM) vs "Pre-processed" (a derived/reconstructed
# image, e.g. a SPECT reconstruction or eddy-corrected DTI) -- both are
# separately downloadable images with their own Image ID, so they are never
# deduplicated here, only counted separately by summarize()/describe_sequences().
TYPE_COL = "Type"

DATE_COLUMNS = ("Study Date", "Archive Date")
NUMERIC_COLUMNS = ("Age", "Weight")


def parse_imaging_protocol(text: str | float) -> dict:
    """Parse the 'key=value;key=value' Imaging Protocol string into a dict.

    Values that look numeric are converted, so e.g. Field Strength can be
    filtered with `df["Field Strength"] >= 3`.
    """
    if not isinstance(text, str):
        return {}

    parsed: dict = {}
    for item in text.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key, value = key.strip(), value.strip()
        try:
            parsed[key] = pd.to_numeric(value)
        except (ValueError, TypeError):
            parsed[key] = value
    return parsed


def expand_imaging_protocol(df: pd.DataFrame, column: str = PROTOCOL_COL) -> pd.DataFrame:
    """Expand the Imaging Protocol string into one column per scanner parameter
    (Manufacturer, Field Strength, Slice Thickness, Acquisition Plane, ...).

    Existing columns are never overwritten: a protocol key that collides with a
    column already in the export is suffixed with ' (protocol)'.
    """
    if column not in df.columns:
        return df

    expanded = pd.DataFrame(
        [parse_imaging_protocol(v) for v in df[column]], index=df.index
    )
    if expanded.empty:
        return df

    renames = {c: f"{c} (protocol)" for c in expanded.columns if c in df.columns}
    expanded = expanded.rename(columns=renames)
    return pd.concat([df, expanded], axis=1)


def normalize_image_ids(values: pd.Series) -> pd.Series:
    """Normalize Image IDs to bare digit strings.

    The website shows and accepts them both as 'I123456' and '123456', and CSV
    round-trips can turn them into floats ('123456.0'); everything is reduced to
    '123456' so IDs from different sources compare equal.
    """
    return (
        values.astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.lstrip("Ii")
    )


def load_ida_search(
    path: str | Path, expand_protocol: bool = True, parse_dates: bool = True
) -> pd.DataFrame:
    """Load an Advanced Image Search export.

    Column names are kept as they appear on the website (only stripped of
    surrounding whitespace) so what you filter on in a notebook matches what you
    ticked in the search form.
    """
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = df.columns.str.strip()

    if IMAGE_ID_COL in df.columns:
        df[IMAGE_ID_COL] = normalize_image_ids(df[IMAGE_ID_COL])

    if parse_dates:
        for col in DATE_COLUMNS:
            if col in df.columns:
                # the search form documents dates as mm/dd/yyyy
                df[col] = pd.to_datetime(df[col], format="%m/%d/%Y", errors="coerce")

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if expand_protocol:
        df = expand_imaging_protocol(df)

    return df


def describe_sequences(
    df: pd.DataFrame,
    by: tuple[str, ...] = (MODALITY_COL, DESCRIPTION_COL),
    image_type: str | None = None,
) -> pd.DataFrame:
    """One row per distinct acquisition Description: how many scans, how many
    subjects, and the date range it spans.

    This is the table to read when deciding which Descriptions map to which BIDS
    modality/suffix -- study Descriptions are free text and notoriously
    inconsistent, so the counts tell you what is worth handling.

    `image_type` restricts to "Original" or "Pre-processed" (see `TYPE_COL`)
    when that column is present -- without it, counts mix raw scanner DICOMs
    with derived/reconstructed images (e.g. SPECT reconstructions), which is
    rarely what you want when scoping a download.
    """
    if image_type is not None and TYPE_COL in df.columns:
        df = df[df[TYPE_COL] == image_type]

    group_cols = [c for c in by if c in df.columns]
    if not group_cols:
        raise ValueError(f"None of {by} present in the export")

    agg = {}
    if IMAGE_ID_COL in df.columns:
        agg["scans"] = (IMAGE_ID_COL, "nunique")
    if SUBJECT_COL in df.columns:
        agg["subjects"] = (SUBJECT_COL, "nunique")
    if DATE_COL in df.columns:
        agg["first"] = (DATE_COL, "min")
        agg["last"] = (DATE_COL, "max")

    out = df.groupby(group_cols, dropna=False).agg(**agg).reset_index()
    sort_col = "scans" if "scans" in out.columns else group_cols[0]
    return out.sort_values(sort_col, ascending=False).reset_index(drop=True)


def visits_per_subject(df: pd.DataFrame) -> pd.Series:
    """Number of distinct visits per subject -- the longitudinal depth of the
    selection. Use `.value_counts().sort_index()` for the distribution."""
    visit_col = VISIT_COL if VISIT_COL in df.columns else DATE_COL
    return df.groupby(SUBJECT_COL)[visit_col].nunique().sort_values(ascending=False)


def modality_availability(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (subject, visit) with a scan count per modality -- who has
    what, and where the multimodal gaps are."""
    visit_col = VISIT_COL if VISIT_COL in df.columns else DATE_COL
    return (
        df.pivot_table(
            index=[SUBJECT_COL, visit_col],
            columns=MODALITY_COL,
            values=IMAGE_ID_COL,
            aggfunc="nunique",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(columns=None)
    )


def summarize(df: pd.DataFrame) -> dict:
    """Headline numbers for a search export, for a quick sanity check."""
    summary: dict = {"rows": len(df)}
    if IMAGE_ID_COL in df.columns:
        summary["images"] = df[IMAGE_ID_COL].nunique()
    if SUBJECT_COL in df.columns:
        summary["subjects"] = df[SUBJECT_COL].nunique()
        counts = visits_per_subject(df)
        summary["visits_total"] = int(counts.sum())
        summary["visits_per_subject_median"] = float(counts.median())
        summary["visits_per_subject_max"] = int(counts.max())
        summary["subjects_longitudinal"] = int((counts > 1).sum())
    if MODALITY_COL in df.columns:
        summary["modalities"] = df[MODALITY_COL].value_counts().to_dict()
    if TYPE_COL in df.columns:
        # Original (raw DICOM) vs Pre-processed (derived/reconstructed) --
        # both count as "images" above, this breaks that total down.
        summary["image_types"] = df[TYPE_COL].value_counts().to_dict()
    if DESCRIPTION_COL in df.columns:
        summary["distinct_descriptions"] = df[DESCRIPTION_COL].nunique()
    if DATE_COL in df.columns and df[DATE_COL].notna().any():
        summary["date_range"] = (
            str(df[DATE_COL].min().date()),
            str(df[DATE_COL].max().date()),
        )
    return summary


def format_image_ids(
    image_ids, chunk_size: int = 1000, prefix: bool = False
) -> list[str]:
    """Format Image IDs as comma-separated strings to paste back into the
    Advanced Search "Image ID" field, which accepts 'I123,I456' or '123,456'.

    Returned as a list of chunks: pasting tens of thousands of IDs into one
    request is rejected, so a large selection is retrieved as several searches.
    """
    ids = normalize_image_ids(pd.Series(list(image_ids))).dropna().unique().tolist()
    ids = [i for i in ids if i and i.lower() != "nan"]
    if prefix:
        ids = [f"I{i}" for i in ids]
    return [
        ",".join(ids[i : i + chunk_size]) for i in range(0, len(ids), chunk_size)
    ]
