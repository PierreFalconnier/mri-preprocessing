# PPMI dataset — context notes

Summary of `PPMI_Overview_Guide_20240918.pdf` and `PPMI_Data_User_Guide_20260806.pdf`
(both in this folder), written for future sessions so the docs don't need
re-reading from scratch. Cross-check against the PDFs directly if something here
looks stale — PPMI data and documentation are both updated continuously with no
formal versioning.

## What PPMI is

The Parkinson's Precision Medicine Initiative (formerly "Progression Markers
Initiative"), launched 2010 by The Michael J. Fox Foundation, is an open-access,
longitudinal, multi-site study collecting biological, clinical, imaging and
genetic markers of Parkinson's onset and progression. It has three data
collection arms with overlapping but distinct participant pools:

| Collection | Captured via | Target N | Content |
|---|---|---|---|
| **PPMI Clinical** | in-person visits | 4,000 | Full battery: MDS-UPDRS (all 4 parts), non-motor assessments, biospecimens, genetics, MRI, DaTscan, medical history. This repo's target. |
| **PPMI Online** | self-report web app | 100,000 | Subset of Clinical (only MDS-UPDRS parts 1-2), own `EVENT_ID` scheme (`OLxx`) |
| **PPMI Remote** | remote/olfactory/genetic screening | 40,000 | Pre-diagnostic-phase focus, tables prefixed `Remote_` |

A fourth, smaller supplementary set, **PPMI FOUND** ("Follow-up of persons with
Neurologic Disease"), adds telephone-follow-up data for some Clinical
participants (risk factors like alcohol use, pesticide exposure, head injury).
Tables are keyed by `PATNO` only, no `EVENT_ID`; dates are in `datacompXX` columns.

Everything downloaded so far under `data/ppmi/` is **PPMI Clinical**.

## 2024/2025 harmonization — why this matters for dates in filenames

PPMI merged its old (2010-2020) and current (2020+) clinical data-capture
systems into one harmonized dataset in 2024. Consequences worth remembering:

- The pre-2020 data now lives in an "Archived PPMI Data" section and should be
  treated as deprecated/static — don't mix it into fresh downloads.
- Some variables/codes were renamed between the two systems; an **annotated**
  data dictionary and code list (`Data_Dictionary_-__Annotated.csv`,
  `Code_List_-__Annotated.csv`, both present in `docs/`) record the old name/code
  next to the new one plus mapping notes. Use these (not a plain dictionary)
  when anything looks inconsistent across years.
- Cohort lookups: use `COHORT` on `Participant_Status`, not the old `APPRDX`.
  `COHORT` codes are consistent with the old `APPRDX` values.
- Genetic Cohort (Unaffected/PD) participants were folded into Prodromal/PD
  respectively; Genetic *Registry* participants are excluded entirely from the
  harmonized data.

**PPMI data has no formal version control** — it's updated nightly/weekly, and
existing values can change, not just have rows added. Always record the
download date (already encoded in our filenames, e.g. `_18Feb2026`) and treat
re-downloads as a new snapshot rather than an incremental update.

## Core identifiers

- **`PATNO`** — unique participant ID, present across Clinical/Online/Remote.
  One known real-world wrinkle: a single participant was enrolled under two
  PATNOs (4067 and 244087); worth a duplicate check if this ever surfaces.
- **`EVENT_ID`** — visit identifier, used with `PATNO` to join any two tables
  at the same timepoint. Clinical scheme: `SC` (screening) → `BL` (baseline) →
  `V01, V02, ...` (scheduled visits) → `R##` (remote-recorded) / `U##`
  (unscheduled). PPMI Online reuses `PATNO` but has its own `OLxx` scheme.
  *As of the Aug 2026 user guide, PPMI's own recommended best practice for
  EVENT_ID in longitudinal analysis is under review — check for a newer guide
  revision before leaning hard on visit-ordering logic.*
- Every measurement table also carries `REC_ID` (row PK), `PAG_NAME` (roughly:
  form/table version), `INFODT` (date measured), `ORIG_ENTRY`/`LAST_UPDATE`.

## Participant categorization (multiple, not always agreeing schemes)

1. **`COHORT`** (`Participant_Status`) — assigned at enrollment, one of:
   Parkinson's Disease, Prodromal, Healthy Control, SWEDD (legacy "scan without
   evidence of dopaminergic deficit", small, often excluded), Early Imaging
   (PD subset with DaTscan/AV-133; can usually be merged into PD).
2. **NSD / NSD-ISS** — biology-first categorization introduced 2024, based on
   the SAA CSF test (pathologic α-synuclein, field `S`) and DaTscan dysfunction
   (field `D`), integrated with genetic status (`G`) into an 8-point **NSD-ISS**
   stage (0, 1A, 1B, 2A, 2B, 3-6). Not yet populated for all participants; only
   in the Curated Data Cut so far, not the raw per-table download.
3. **Genetic subgroup** columns on `Participant_Status`
   (`ENRLPINK1/PRKN/SRDC/HPSM/RBD/LRRK2/SNCA/GBA`) — sporadic vs. which known PD
   risk variant, set at enrollment; RBD/HPSM prodromal cases keep their original
   designation even if they later convert to PD.
4. **`ENROLL_STATUS`** — Pending/Screened/Declined/Screen_failed/Excluded/
   **Enrolled/Withdrew/Complete**. Almost always want to filter to the last
   three; note inconsistent capitalization in the raw values ("Withdrew" vs.
   "withdrew").

These schemes don't always agree (cohort = clinical judgment, NSD = biological
assay) — pick deliberately per research question rather than assuming one
supersedes the others.

## What's actually on disk here

- `docs/` — `PPMI_Overview_Guide_20240918.pdf`, `PPMI_Data_User_Guide_20260806.pdf`
  (this note summarizes both), `Data_Dictionary_-__Annotated.csv`,
  `Code_List_-__Annotated.csv`, `PPMI_Curated_Data_Cut_Public_20251112.xlsx`
  (sheets: `20251013` data, `Data dictionary`, `Information` — a pre-joined,
  denormalized single table, 3096 participants / ~160 columns as of its own Jan
  2024 extract date, does **not** yet include NSD-ISS for all rows), and
  `PPMI_Biomarkers_Dashboard_20240819.xlsx` (sheets: `Dashboard Info`,
  `19Aug2024` data, `Data Dictionary`, `Project Info` — biospecimen/proteomic
  project tracker, not yet inspected in detail).
- `ida_search/idaSearch_18Feb2026.csv` — 81,436 rows, the ida.loni Advanced
  Image Search export. Columns: `Subject ID, Project, Sex, Weight, Research
  Group, Visit, Study Date, Archive Date, Age, GDSCALE Total Score, Modality,
  Description, Type, Imaging Protocol, Image ID, Structure, Laterality, Image
  Type, Registration, Tissue`. This is the image-level inventory (one row per
  scan) used to pick which Image IDs to download — `Subject ID` joins to
  `PATNO`, `Description`/`Modality` need the same kind of hand-curated mapping
  to BIDS categories described for the previous repo layout (see git history /
  AGENTS.md), `Research Group` is the ida.loni-side cohort label (compare
  against `COHORT` after download, they aren't guaranteed to agree).
- `study/*.csv` — 19 PPMI Clinical tables actually downloaded so far:
  `Participant_Status`, `Demographics`, `Age_at_visit`, `Socio-Economics`,
  `Clinical_Diagnosis`, `Primary_Clinical_Diagnosis`; MDS-UPDRS Parts I
  (+ Patient Questionnaire), II (Patient Questionnaire), III, IV; cognitive/
  motor batteries `Benton_Judgement_of_Line_Orientation`, `Clock_Drawing`,
  `Letter_-_Number_Sequencing`, `Modified_Boston_Naming_Test`,
  `Modified_Semantic_Fluency`, `Montreal_Cognitive_Assessment__MoCA_`,
  `Symbol_Digit_Modalities_Test`, `University_of_Pennsylvania_Smell_
  Identification_Test_UPSIT`. No biospecimen, genetics, medication (LEDD), or
  raw MRI/DaTscan metadata tables downloaded yet — see "Not yet downloaded"
  below if/when the tabular side needs them.

## Imaging data (for when the MRI stage starts)

- Image metadata (separate from pixel data) lives in tables like
  `Magnetic_Resonance_Imaging__MRI_` — same `PATNO`/`EVENT_ID`/`INFODT` keys as
  everything else, plus MRI-specific fields: `MRICMPLT` (completed y/n),
  `MRIRSLT` (1 normal / 2 abnormal-not-significant / 3 abnormal-significant),
  `MRIWDTI` (has DTI), `MRIWRSS` (has resting-state), `PDMEDDT`/`PDMEDTM` (last
  dopaminergic dose date/time before the scan — relevant since medication state
  can affect imaging/motor findings).
- Actual DICOM/NIfTI pixel data is downloaded separately via the ida.loni image
  search/download tool (the `ida_search/` CSV above is that tool's export), not
  through the Study Data tabular download.
- Preprocessing target for this project stays `MNI152_T1_1mm_brain_RAS.nii.gz`
  (RAS-reoriented FSL template) per the existing pipeline scripts.

## Medication (LEDD)

Dopaminergic medication is stored as **Levodopa Equivalent Daily Dose (LEDD)**
in `LEDD_Concomitant_Medication_Log` — one row per drug per active date-range
(`STARTDT`/`STOPDT`, open-ended `STOPDT` = still prescribed), not one row per
visit. Conversion rules (levodopa itself counted at face value minus enzyme
inhibitor; dopamine agonists and MAO-B inhibitors converted via fixed
multipliers; COMT inhibitors scaled by the levodopa dose) are in Tomlinson et
al. (2010). To get "total LEDD at time X" you must reconstruct a
change-point series across all concurrent drugs (the guide's Appendix has an
R/SQL script, `Script 7`, that does this) — a naive per-row read is not usable
directly. Non-dopaminergic drugs are in the separate `Concomitant_Medication_Log`
table with no unit conversion. Not downloaded yet in this repo.

## Genetics (for later)

Multiple layers of genetic data exist, from a simple "is participant a
carrier of a known high-risk PD variant" flag (`Participant_Status` columns)
up through raw WGS/WES/RNA-seq (very large — WGS alone ~184TB raw, so raw
'omics is on-request only, not part of the standard tabular download). For a
longitudinal/multimodal DL project, the enrollment-time genetic subgroup flags
and possibly the curated `PPM_Project_9001` polygenic risk score are the
practically-sized starting points; raw sequencing is out of scope unless a
specific need arises.

## Practical notes for building the cleaning pipeline

- **`PATNO` + `EVENT_ID`** is the join key for essentially everything in
  Clinical; a single "long" table per assessment, joined on those two columns,
  is the natural shape — matches how PPMI itself ships the data.
- Every raw file needs its **date suffix stripped or tracked** (they change
  per download) before any script assumes a fixed filename.
- Several assessment tables need **row-to-summary aggregation** before they're
  usable as a single per-visit variable (e.g. MoCA sub-item scores → total;
  LEDD log → point-in-time dose) — check the annotated data dictionary's
  "Derived Variable" column before re-deriving something PPMI's own Curated
  Data Cut already computed.
- The **Curated Data Cut** (`PPMI_Curated_Data_Cut_Public_20251112.xlsx`) is
  PPMI's own pre-joined, denormalized table (~160 columns) and may be a faster
  path to a first usable tabular dataset than joining ~19+ raw tables by hand —
  worth comparing coverage/freshness against the raw tables before committing
  to one approach.
- `ida_search` `Description`/`Modality` free text needs the same kind of
  manual, versioned curation-to-BIDS-modality mapping this project already
  applied for PPMI in a previous repo layout — don't try to infer it purely
  from string matching.

## Not yet downloaded (known gaps as of this note)

Biospecimen/CSF results (amyloid-beta, tau, SAA), DaTscan SBR values, raw MRI
image metadata table, medication (LEDD) log, and all genetics tables are
described in the user guide but not present under `data/ppmi/study/` yet.
Pull them from the ida.loni Study Data download page (Section 3.6 of the user
guide lists the recommended starter set) as the tabular-cleaning work reaches
those variables.
