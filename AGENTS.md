# AGENTS.md

Guidance for AI coding agents working in this repository. Human-facing
documentation lives in [README.md](README.md) -- read it first; this file only
adds the conventions and constraints that are not obvious from the code.

## What this repo is

A pipeline turning ida.loni imaging downloads and clinical CSV exports into a
curated BIDS dataset plus a queryable merged tabular dataset, for a PhD on
longitudinal/multimodal representation learning in Parkinson's disease (PPMI
first, ADNI and others later). Everything is meant to be reused across studies:
dataset-specific knowledge belongs behind an adapter, never in a stage.

## Ground rules

1. **No hardcoded paths.** Every path comes from `configs/datasets/<name>.yaml`
   via `mri_prep.config.load_dataset_config`. Relative paths in a config resolve
   against the repo root; `~` is expanded. If you need a new path, add it to
   `DatasetPaths` or to the config's `extra` dict -- do not inline it.
2. **Dataset-specific logic goes in an adapter.** `src/mri_prep/datasets/<name>.py`
   implements `build_bids_name` / `iter_source_images` / `load_tabular`
   (see `datasets/base.py`). Sequence-description regexes, visit-code maps,
   diagnosis code maps and the like belong there. A stage under `bids/`,
   `preprocess/`, `qc/`, `export/` or `tabular/` that grows an `if dataset ==`
   branch is a bug.
3. **Imaging data never enters the repo.** Only tabular data and small generated
   tables live under `data/`. NIfTI/DICOM/npy trees live wherever the dataset
   config points (external drive, cluster scratch).
4. **The CLI is a thin shell.** `cli.py` parses options, loads the config and
   calls a library function. Keep the logic importable from a notebook; imports
   inside command bodies are deliberate (CLI startup speed).

## Steps 1-5 stay collaborative

Cohort selection -- exploring a search export, reading the study PDFs, deciding
which acquisition Descriptions map to which BIDS suffix, choosing the clinical
variables -- requires domain judgment and the study documentation. Do **not**
try to automate those away behind a single command. The right contribution is
reusable parsing/querying helpers (`mri_prep.tabular.ida`, which is
study-agnostic because the ida.loni export schema is identical across studies)
plus notebooks to drive them. Steps 6-7 (imaging pipeline, final dataset
assembly) are the ones that should be fully automated and config-driven.

## Where data files go

Per dataset, under `data/<DATASET>/`:

| Directory | Contents |
|---|---|
| `search/` | ida.loni Advanced Image Search exports (`idaSearch_*.csv`) |
| `study/` | Study Data downloads: clinical/assessment CSVs, Data Dictionary, Code List |
| `docs/` | PDFs, protocol and dataset-description documents |
| `tabular/` | **generated** outputs only (merged tables, per-image metadata) |

`data/PPMI/csv/{ALL,CLINICAL,OTHERS}` is the pre-refactor layout (overlapping
copies, image search export mixed in with clinical CSVs) and is being retired;
`paths.csv_root` still points there until the fresh downloads land.

## Working conventions

- **Environment**: `uv sync`, then `uv run mri-prep ...`. Do not add
  dependencies without checking resolution -- `intensity-normalization==2.2.4`
  pins `nibabel<4`, which constrains everything downstream.
- **External binaries**: `dcm2niix` for conversion; ANTs + FreeSurfer
  (`N4BiasFieldCorrection`, `antsRegistrationSyNQuick.sh`, `mri_synthstrip`,
  `mri_synthseg`) for preprocessing. They may be absent locally; code must fail
  with a clear message rather than half-run.
- **Verify on real data**, not just on imports. The PPMI tables and a search
  export are in the repo: run `mri-prep tabular merge --dataset ppmi` or
  `mri-prep ida summary --csv ...` and check the counts are plausible before
  claiming a stage works.
- **Long-running stages are resumable.** Preprocessing and QC run over tens of
  thousands of scans on a PBS cluster; skip work whose output already exists,
  and make sure that skip path does not reference variables only set on the
  compute path.
- **`legacy/`** holds the pre-refactor scripts, kept only as reference until the
  new pipeline is verified end-to-end. Port from it; do not extend it, and do
  not import from it.

## Style

Match the surrounding code: `from __future__ import annotations`, typed
signatures, module docstrings that say *why* a module exists and show the
typical call, and comments reserved for non-obvious domain facts (why a visit
code maps the way it does, why a threshold is what it is). No decorative
comments restating the code.
