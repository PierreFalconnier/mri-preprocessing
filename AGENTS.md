# AGENTS.md

Guidance for AI coding agents working in this repository. Human-facing
documentation lives in [README.md](README.md) -- read it first; this file only
adds conventions and constraints that aren't obvious from the code.

## What this repo is

A pipeline turning ida.loni (ida.loni.usc.edu) DICOM downloads and clinical CSV
exports into a curated, BIDS-organized, QC'd imaging dataset, for a PhD on
longitudinal/multimodal representation learning in Parkinson's disease
(PPMI-first; ADNI, OASIS, WRAP, HABS, MCSA and others explored under
`csv_exploration/ida_explo/`). It is currently a collection of standalone
scripts and notebooks organized by pipeline stage, not an installable
package -- there is no shared library layer, so a script imports what it
needs directly and duplication between similar scripts (e.g. the several
`turboprep-multiple*.py` variants) is expected rather than a bug to eliminate
on sight.

## Layout

| Directory | Contents |
|---|---|
| `csv_exploration/` | Per-dataset notebooks exploring ida.loni search exports and metadata (`ida_explo/`, `PPMI_explo/`, `others/`) |
| `csv_dir/` | Raw/derived CSV and Excel metadata per dataset |
| `bash_scripts/` | Merge/extract/flatten shell scripts, npy export, misc dataset scripts; `old_bash_scripts/` is superseded, kept for reference only |
| `PPMI_to_bids/` | PPMI-specific DICOM -> BIDS conversion |
| `preprocessing/` | turboprep (N4, registration, brain extraction) job scripts + PBS files for the cluster |
| `quality_control/` | QC metrics computation, outlier detection, PBS submission scripts |
| `exploration_scripts/` | Ad hoc visualization/inspection scripts (gifs, 3D viz, RAS orientation checks) |
| `MNI_templates/` | MNI152 templates, including RAS-reoriented variants used as the preprocessing target |
| `unused_code/` | Retired/superseded scripts kept for reference -- do not build on these, and do not "clean them up" unless asked |
| `data/`, `logs/` | Local, gitignored outputs and downloads |

## Ground rules

1. **No package, no shared imports across top-level dirs.** Scripts are meant
   to be self-contained and runnable on their own (locally or via a PBS job).
   Don't introduce a `src/`-style package or cross-directory imports unless
   explicitly asked -- that's a larger refactor, not a byproduct of a small fix.
2. **Dataset-specific logic stays inline in that dataset's script**, not
   behind a generic abstraction. There's no adapter layer here (unlike a
   fully config-driven pipeline) -- PPMI-specific parsing lives in
   `PPMI_to_bids/` and `csv_exploration/PPMI_explo/`, and similar future work
   for other datasets should follow the same pattern rather than trying to
   generalize prematurely across datasets that haven't been explored yet.
3. **Imaging data never enters the repo.** Only small CSV/metadata files
   belong under `csv_dir/`/`data/`. DICOM/NIfTI/npy trees live on external
   drives or cluster scratch, referenced by path in scripts/PBS files, never
   committed.
4. **RAS orientation matters.** Preprocessing targets
   `MNI152_T1_1mm_brain_RAS.nii.gz` specifically (a reoriented variant of the
   standard FSL template) so that all preprocessed outputs stay in RAS. Don't
   swap in a different template variant without checking orientation.

## Steps 1-4 stay collaborative

Cohort selection and metadata curation -- exploring an ida.loni search export,
reading study documentation, deciding which acquisition Descriptions map to
which sequence/modality, choosing which clinical variables matter -- requires
domain judgment and the study's own documentation. Do not try to automate
those steps away behind a single script; the right contribution is
notebook-driven exploration (as in `csv_exploration/`) that leaves the
decisions to the user. The imaging pipeline from flatten/BIDS-conversion
onward (steps 5-8 in README.md) is the part that should be fully automated
and scriptable.

## Working conventions

- **Environment**: managed with `uv` -- `uv sync`, then `uv run <script>.py`.
- **External binaries**: `dcm2niix` for DICOM->NIfTI conversion; ANTs +
  FreeSurfer tooling (`N4BiasFieldCorrection`, `antsRegistrationSyNQuick.sh`,
  `mri_synthstrip`, `mri_synthseg`) for preprocessing. These may be absent
  locally -- scripts should fail with a clear message rather than half-run,
  and cluster-only steps are expected to only run correctly via the PBS jobs.
- **Cluster jobs are resumable/parallel.** Preprocessing and QC run over tens
  of thousands of scans via PBS (`run_turboprep_jobs.sh`, `run_qc_job.pbs`,
  `submit_all_qc.sh`); when touching these, preserve the ability to skip work
  whose output already exists and to run many jobs in parallel.
- **Verify against real data before claiming a stage works** -- check output
  counts/paths are plausible, not just that the script runs without error.
