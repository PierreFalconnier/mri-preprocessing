# mri-prep

MRI + tabular data pipeline for neurodegenerative disease progression modeling
(PhD project: longitudinal, multimodal representation learning for Parkinson's
disease subtyping, PPMI-first). Turns raw ida.loni DICOM downloads and clinical
CSV exports into a curated, BIDS-organized, QC'd imaging dataset plus a
queryable merged tabular dataset -- both usable directly for exploration and
for training ML/DL models.

Everything dataset-specific (PPMI, ADNI, ...) lives behind a small adapter +
a YAML config; the pipeline stages themselves (BIDS conversion, preprocessing,
QC, export, tabular merge) are generic and shared.

## Layout

```
configs/datasets/<name>.yaml   one config per dataset: paths, template, adapter
src/mri_prep/                  the package (installable, `mri-prep` CLI)
  config.py                    DatasetConfig loading/resolution
  datasets/                    per-dataset adapters (BIDS naming, raw layout, CSV loading)
  bids/                        flatten -> convert -> index a BIDS tree
  preprocess/                  turboprep (N4, SynthStrip, registration, SynthSeg, WhiteStripe), reorganize
  qc/                          QC metrics, outlier detection, curated-subset symlinks
  export/                      final npy export for training
  tabular/                     ida.loni search exports, CSV merge, Cohort query API
  cli.py                       `mri-prep <group> <command> --dataset <name>`
data/<DATASET>/                tracked tabular data (raw CSVs, merged tables) -- imaging data itself
                                lives outside the repo (see paths in the dataset config)
templates/                     MNI152 templates (RAS-reoriented variants included)
notebooks/                     interactive exploration (cohort/sequence selection, CSV QA)
scripts/                       cluster job submission (PBS) wrapping the CLI
legacy/                        pre-refactor scripts/notebooks, kept for reference until
                                fully ported (see "What's not migrated yet" below)
```

## Setup

```bash
uv sync
uv run mri-prep --help
```

Requires `dcm2niix` on PATH for BIDS conversion, and ANTs +
FreeSurfer (`N4BiasFieldCorrection`, `antsRegistrationSyNQuick.sh`,
`mri_synthstrip`, `mri_synthseg`) on PATH for preprocessing.

## End-to-end, in order

The two sections below ("Selecting a cohort", "Processing images") give the
detail; this is the shape of the whole pipeline, PPMI-first, in the order
you actually run it:

1. Search ida.loni, download the search export -> `data/<DATASET>/search/`.
2. Explore it (`mri-prep ida summary`/`sequences`) and curate the Description
   -> BIDS-modality mapping until `uncategorized` is small.
3. Download the clinical/assessment CSVs -> `data/<DATASET>/study/`, study
   docs -> `data/<DATASET>/docs/`.
4. Filter to your selection, build the download list
   (`mri-prep ida image-ids`), download + extract the images.
5. `mri-prep bids flatten` the extracted tree.
6. Build the per-image metadata table (`extra.merged_csv`) --
   `notebooks/ppmi_imaging_exploration.ipynb` for PPMI.
7. `mri-prep bids convert` -> BIDS.
8. `mri-prep preprocess turboprep` (N4, skull strip, register, segment,
   normalize).
9. `mri-prep preprocess reorganize`, then `mri-prep qc run --curate`.
10. `mri-prep export npy` for training-ready arrays.
11. `mri-prep tabular merge` / `mri_prep.tabular.cohort.Cohort` to get the
    matching clinical table for whatever subject/visit selection you end up
    with.

## Dataset configs

Each dataset is one file in `configs/datasets/`, e.g. `configs/datasets/ppmi.yaml`:

```yaml
name: ppmi
adapter: ppmi
paths:
  raw_dicom_root: ~/data/PPMI/raw_dicom
  flattened_root: ~/data/PPMI/flattened
  bids_root: ~/data/PPMI/bids
  preprocessed_root: ~/data/PPMI/bids_processed
  curated_root: ~/data/PPMI/bids_curated
  csv_root: data/PPMI/study      # relative paths resolve against the repo root
  qc_csv: ~/data/PPMI/qc/ppmi_qc.csv
template: templates/MNI152_T1_1mm_brain_RAS.nii.gz
template_mask: templates/MNI152_T1_1mm_brain_mask_RAS.nii.gz
modality: t1
extra:
  merged_csv: data/PPMI/tabular/ppmi_imaging_metadata.csv
```

Edit the `~/data/...` paths to wherever the actual imaging data lives on your
machine/cluster (external drive, scratch space, ...) -- imaging data is never
meant to live inside the git repo. Adding a new dataset = add a config +
(if its raw layout / naming differs) a small adapter in `src/mri_prep/datasets/`
implementing `build_bids_name` / `iter_source_images` / `load_tabular`
(see `datasets/base.py` for the interface, `datasets/ppmi.py` for a full example).

## Selecting a cohort

These steps are interactive by design -- deciding which acquisitions and which
clinical variables matter needs the study documentation and your judgment. The
CLI/library here does the parsing and counting; the decisions stay yours.

1. **Search** on ida.loni (Advanced Image Search), tick the "display in result"
   boxes you care about, and download the results CSV into `data/<DATASET>/search/`.
2. **Explore the export**:

   ```bash
   mri-prep ida summary   --csv data/ADNI/search/idaSearch_2026.csv
   mri-prep ida sequences --csv data/ADNI/search/idaSearch_2026.csv --modality MRI
   ```

   `summary` gives subjects/visits/modalities/date range (and surfaces junk rows);
   `sequences` lists every distinct acquisition `Description` with scan and
   subject counts -- the table to read when mapping Descriptions to BIDS
   suffixes. From Python, `mri_prep.tabular.ida.load_ida_search` also expands the
   `Imaging Protocol` string into real columns (Field Strength, Manufacturer,
   Slice Thickness, Acquisition Plane, ...) so you can filter on them.
3. **Add the study documents** -- PDFs, data dictionaries, protocol descriptions --
   to `data/<DATASET>/docs/`, and the subject tabular data (clinical/assessment
   CSVs, `paths.csv_root`) to `data/<DATASET>/study/`.
4. **Pick the clinical variables** per subject and visit from those documents,
   and merge them with `mri-prep tabular merge` (see below).
5. **Get the images**: filter the export down to your selection in a notebook,
   then

   ```bash
   mri-prep ida image-ids --csv my_selection.csv --out ids.txt
   ```

   emits comma-separated blocks to paste into the Advanced Search "Image ID"
   field, which is how you build the download collection. Download it (a
   download manager such as jDownloader handles the multi-part zips), and
   extract.

## Processing images

1. **Flatten**: `mri-prep bids flatten --dataset ppmi`
   -- normalizes the nested ida.loni folder layout into `sub-*/ses-YYYYMMDD/<sequence>/`.
2. **Build the per-image metadata table**: curate the ida.loni search export's
   Descriptions into a BIDS modality (`mri_prep.datasets.ppmi.annotate_categories`
   -- extend `ppmi_description_categories.json`/`ppmi_ignored_descriptions.csv`
   as new Descriptions turn up), filter to the usable image rows, join with
   the clinical table, and save to `data/<DATASET>/tabular/` as the
   `extra.merged_csv` named in the dataset config. `bids/convert.py` looks up
   each raw image by `Image ID` and reads `PATNO`/`EVENT_ID`/`BIDS_Modality`
   (+ `Advanced_Modality`, `Acquisition Plane`, ... for `build_bids_name`) off
   the matching row, so those columns must be present. For PPMI this is
   `notebooks/ppmi_imaging_exploration.ipynb` (optional exploratory analysis
   of the resulting table lives separately in
   `notebooks/ppmi_cohort_exploration.ipynb`, since nothing downstream
   depends on it).
3. **Convert to BIDS**: `mri-prep bids convert --dataset ppmi`
   -- walks the flattened tree, matches each image to its metadata row, asks
   the dataset adapter for a BIDS filename, runs `dcm2niix`.
4. **Preprocess T1w** (cluster): `scripts/submit_turboprep_jobs.sh ppmi <SRC> <DST> <NUM_JOBS>`
   splits the file list and submits one `scripts/pbs/turboprep.pbs` job per
   chunk, each running `mri-prep preprocess turboprep`. Locally / single node:
   `mri-prep preprocess turboprep --dataset ppmi --inputs inputs.txt --outputs outputs.txt`.
5. **Reorganize**: `mri-prep preprocess reorganize --dataset ppmi`
   -- flattens turboprep's per-run subdirectories into prefixed files
   (symlinks) so downstream code can glob by suffix directly.
6. **QC**: `mri-prep qc run --dataset ppmi --curate [--mosaics]`
   -- computes dice-vs-MNI-mask, tissue SNR/CNR/CJV/WM2MAX, flags outliers
   (robust median/MAD), writes an interactive HTML report, and (with
   `--curate`) symlinks a QC-passed subset into `paths.curated_root`.
7. **Export for training**: `mri-prep export npy --dataset ppmi --pattern "*brain.nii.gz"`
   -- RAS-orients, resamples to 1mm isotropic, crops to foreground, min-max
   normalizes, saves `.npy` next to each source file.

At any point: `mri-prep bids index --dataset ppmi --stage bids --out index.csv`
builds a flat (subject, session, suffix, run, path) index of a BIDS/processed
tree -- the basis for modality-availability queries.

## Tabular data / cohort selection

```bash
mri-prep tabular merge --dataset ppmi --out data/PPMI/tabular/ppmi_clinical_merged.csv
```

merges every raw clinical CSV under `paths.csv_root` into one wide table,
keyed on subject id (+ visit id for visit-level tables, left-joined for
subject-level ones). From Python:

```python
from mri_prep.tabular.cohort import Cohort

cohort = (
    Cohort.from_dataset("ppmi")
    .where(COHORT="Parkinson's Disease")
    .with_min_visits(3)
    .with_modality("T1w", bids_root="~/data/PPMI/bids_curated")
)
cohort.subjects        # matching PATNOs
cohort.table           # filtered merged DataFrame
cohort.to_csv("my_cohort.csv")
```

`Cohort` is the intended one-stop way to go from "I want PD subjects with
>=3 visits and a usable T1w at every visit" to an exact subject/row list,
without hand-rolling pandas joins each time.

## What's not migrated yet

`legacy/` holds everything from before this refactor, kept for reference:

- `legacy/bash_scripts/` -- 2D slicing (`3d_to_2d_dataset.py`), simple npy
  export without yucca, npy viewers, ADNI-specific reorganization script.
  Port into `src/mri_prep/export/` / `src/mri_prep/datasets/adni.py` as
  ADNI work resumes (see the stub in `src/mri_prep/datasets/adni.py`).
- `legacy/exploration_scripts/` -- ad hoc RAS-orientation and 3D
  visualization scripts.
- `legacy/csv_exploration/` -- prior exploration notebooks and dated CSV
  snapshots (the canonical output is now `data/PPMI/tabular/ppmi_imaging_metadata.csv`
  + `notebooks/ppmi_imaging_exploration.ipynb`).
- `legacy/PPMI_to_bids/`, `legacy/preprocessing/`, `legacy/quality_control/` --
  fully superseded by `src/mri_prep/bids`, `src/mri_prep/preprocess`,
  `src/mri_prep/qc`; kept only until the new code has been exercised on a
  full re-run.

Once you've run the new pipeline end-to-end on PPMI and are confident it
reproduces the old outputs, `legacy/` can be deleted.
