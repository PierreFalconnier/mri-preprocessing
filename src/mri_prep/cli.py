"""Unified CLI for the MRI + tabular data pipeline.

Every stage takes `--dataset <name>` and reads its paths from
`configs/datasets/<name>.yaml` (see `mri_prep.config`), so the same commands
work across PPMI/ADNI/... once a dataset has a config + adapter.

    mri-prep bids flatten --dataset ppmi
    mri-prep bids convert --dataset ppmi
    mri-prep bids index --dataset ppmi --stage bids
    mri-prep tabular merge --dataset ppmi -o data/PPMI/tabular/ppmi_merged.csv
    mri-prep preprocess turboprep --dataset ppmi --inputs inputs.txt --outputs outputs.txt
    mri-prep preprocess reorganize --dataset ppmi
    mri-prep qc run --dataset ppmi --curate
    mri-prep export npy --dataset ppmi --pattern "*brain.nii.gz"
"""

from __future__ import annotations

from pathlib import Path

import typer

from mri_prep.config import list_datasets, load_dataset_config

app = typer.Typer(no_args_is_help=True, help=__doc__)
ida_app = typer.Typer(no_args_is_help=True, help="Explore ida.loni Advanced Search exports")
bids_app = typer.Typer(no_args_is_help=True, help="Raw DICOM -> BIDS")
preprocess_app = typer.Typer(no_args_is_help=True, help="T1w preprocessing (turboprep)")
qc_app = typer.Typer(no_args_is_help=True, help="Quality control")
export_app = typer.Typer(no_args_is_help=True, help="Export preprocessed volumes for training")
tabular_app = typer.Typer(no_args_is_help=True, help="Tabular/clinical data merge + cohort queries")

app.add_typer(ida_app, name="ida")
app.add_typer(bids_app, name="bids")
app.add_typer(preprocess_app, name="preprocess")
app.add_typer(qc_app, name="qc")
app.add_typer(export_app, name="export")
app.add_typer(tabular_app, name="tabular")


@app.command("datasets")
def datasets_cmd():
    """List datasets with a config in configs/datasets/."""
    for name in list_datasets():
        typer.echo(name)


# -- ida ----------------------------------------------------------------


@ida_app.command("summary")
def ida_summary(csv: Path = typer.Option(..., help="Advanced Search export CSV")):
    """Headline numbers for a search export: subjects, visits, modalities, dates."""
    from mri_prep.tabular.ida import load_ida_search, summarize

    info = summarize(load_ida_search(csv))
    for key, value in info.items():
        if isinstance(value, dict):
            typer.echo(f"{key}:")
            for k, v in value.items():
                typer.echo(f"  {k}: {v}")
        else:
            typer.echo(f"{key}: {value}")


@ida_app.command("sequences")
def ida_sequences(
    csv: Path = typer.Option(..., help="Advanced Search export CSV"),
    modality: str = typer.Option(None, help="restrict to one modality, e.g. MRI"),
    type: str = typer.Option(
        None, help="restrict to one Type, e.g. Original or 'Pre-processed'"
    ),
    top: int = typer.Option(40, help="how many descriptions to show"),
    out: Path = typer.Option(None, help="optional CSV to write the full table to"),
):
    """List the distinct acquisition Descriptions with scan/subject counts --
    the starting point for mapping Descriptions to BIDS modalities."""
    import pandas as pd

    from mri_prep.tabular.ida import MODALITY_COL, describe_sequences, load_ida_search

    df = load_ida_search(csv)
    if modality:
        df = df[df[MODALITY_COL] == modality]

    table = describe_sequences(df, image_type=type)
    with pd.option_context("display.max_rows", None, "display.width", 200):
        typer.echo(table.head(top).to_string(index=False))
    if len(table) > top:
        typer.echo(f"... {len(table) - top} more (use --top or --out)")
    if out:
        table.to_csv(out, index=False)
        typer.echo(f"Wrote full table to {out}")


@ida_app.command("image-ids")
def ida_image_ids(
    csv: Path = typer.Option(..., help="Export CSV, or your filtered selection of it"),
    out: Path = typer.Option(None, help="write chunks to this file (one per block)"),
    chunk_size: int = typer.Option(1000, help="Image IDs per search request"),
    prefix: bool = typer.Option(False, help="emit I-prefixed ids (I123) instead of 123"),
):
    """Emit the selection's Image IDs as comma-separated blocks, ready to paste
    into the Advanced Search "Image ID" field to build the download collection."""
    from mri_prep.tabular.ida import IMAGE_ID_COL, format_image_ids, load_ida_search

    df = load_ida_search(csv, expand_protocol=False, parse_dates=False)
    chunks = format_image_ids(df[IMAGE_ID_COL], chunk_size=chunk_size, prefix=prefix)
    n_ids = sum(c.count(",") + 1 for c in chunks if c)

    if out:
        out.write_text("\n\n".join(chunks) + "\n")
        typer.echo(f"{n_ids} image ids in {len(chunks)} block(s) -> {out}")
    else:
        for i, chunk in enumerate(chunks, start=1):
            typer.echo(f"--- block {i}/{len(chunks)} ---")
            typer.echo(chunk)


# -- bids ----------------------------------------------------------------


@bids_app.command("flatten")
def bids_flatten(dataset: str = typer.Option(...)):
    from mri_prep.bids.flatten import flatten_ida_download

    cfg = load_dataset_config(dataset)
    flatten_ida_download(cfg.paths.raw_dicom_root, cfg.paths.flattened_root)


@bids_app.command("convert")
def bids_convert(dataset: str = typer.Option(...)):
    from mri_prep.bids.convert import convert_to_bids

    cfg = load_dataset_config(dataset)
    convert_to_bids(cfg)


@bids_app.command("index")
def bids_index(
    dataset: str = typer.Option(...),
    stage: str = typer.Option("bids", help="which path in the config to index: bids|preprocessed|curated"),
    pattern: str = typer.Option("*.nii.gz"),
    out: Path = typer.Option(None, help="optional CSV to save the index to"),
):
    from mri_prep.bids.index import index_bids_tree

    cfg = load_dataset_config(dataset)
    root = {
        "bids": cfg.paths.bids_root,
        "preprocessed": cfg.paths.preprocessed_root,
        "curated": cfg.paths.curated_root,
    }[stage]
    index = index_bids_tree(root, pattern)
    typer.echo(f"{len(index)} files indexed under {root}")
    if out:
        index.to_csv(out, index=False)
        typer.echo(f"Saved index to {out}")


# -- preprocess ------------------------------------------------------------


@preprocess_app.command("turboprep")
def preprocess_turboprep(
    dataset: str = typer.Option(...),
    inputs: Path = typer.Option(..., help="text file, one input image path per line"),
    outputs: Path = typer.Option(..., help="text file, one output dir per line"),
    threads: int = typer.Option(1),
):
    from mri_prep.preprocess.turboprep import run_turboprep

    cfg = load_dataset_config(dataset)

    def _read_lines(p: Path) -> list[str]:
        return [line.strip() for line in p.read_text().splitlines() if line.strip()]

    run_turboprep(
        inputs=_read_lines(inputs),
        outputs=_read_lines(outputs),
        template=str(cfg.template),
        modality=cfg.modality,
        threads=threads,
    )


@preprocess_app.command("reorganize")
def preprocess_reorganize(
    dataset: str = typer.Option(...),
    destination: Path = typer.Option(None, help="defaults to <preprocessed_root>_flat"),
):
    from mri_prep.preprocess.reorganize import reorganize_preprocessed

    cfg = load_dataset_config(dataset)
    dest = destination or Path(f"{cfg.paths.preprocessed_root}_flat")
    reorganize_preprocessed(cfg.paths.preprocessed_root, dest)


# -- qc ----------------------------------------------------------------


@qc_app.command("run")
def qc_run(
    dataset: str = typer.Option(...),
    threshold: float = typer.Option(0.92, help="MNI dice threshold"),
    curate: bool = typer.Option(False, help="create a curated (symlinked) outlier-free copy"),
    mosaics: bool = typer.Option(False, help="generate outlier mosaic images (slow)"),
):
    from mri_prep.qc.metrics import main as qc_main

    cfg = load_dataset_config(dataset)
    qc_main(
        source_root=cfg.paths.preprocessed_root,
        mni_mask_path=cfg.template_mask,
        output_csv=cfg.paths.qc_csv,
        threshold=threshold,
        curated_dir=cfg.paths.curated_root if curate else None,
        make_mosaics=mosaics,
    )


# -- export ----------------------------------------------------------------


@export_app.command("npy")
def export_npy(
    dataset: str = typer.Option(...),
    pattern: list[str] = typer.Option(["*brain.nii.gz"]),
    jobs: int = typer.Option(2),
):
    from mri_prep.export.to_npy import export_dataset_to_npy

    cfg = load_dataset_config(dataset)
    root = cfg.paths.curated_root or cfg.paths.preprocessed_root
    export_dataset_to_npy(str(root), list(pattern), jobs)


# -- tabular ----------------------------------------------------------------


@tabular_app.command("merge")
def tabular_merge(
    dataset: str = typer.Option(...),
    out: Path = typer.Option(..., help="output CSV path"),
    subject_col: str = typer.Option("PATNO"),
    visit_col: str = typer.Option("EVENT_ID"),
):
    from mri_prep.datasets import get_adapter
    from mri_prep.tabular.merge import merge_dataset_tables

    cfg = load_dataset_config(dataset)
    adapter = get_adapter(cfg.adapter)
    tables = adapter.load_tabular(cfg.paths.csv_root)
    merged = merge_dataset_tables(tables, subject_col=subject_col, visit_col=visit_col)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out, index=False)
    typer.echo(f"Merged {len(tables)} tables -> {len(merged)} rows, {merged[subject_col].nunique()} subjects -> {out}")


@tabular_app.command("cohort-info")
def tabular_cohort_info(dataset: str = typer.Option(...)):
    """Quick sanity check: subject/visit counts for a dataset's merged table."""
    from mri_prep.tabular.cohort import Cohort

    cohort = Cohort.from_dataset(dataset)
    typer.echo(f"{len(cohort)} subjects, {len(cohort.table)} rows")


if __name__ == "__main__":
    app()
