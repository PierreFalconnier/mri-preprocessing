"""T1w preprocessing: N4 bias correction, SynthStrip, affine registration to
a template, SynthSeg segmentation, brain mask + WhiteStripe intensity
normalization.

Ported from the legacy `preprocessing/turboprep-multiple-v2.py` (itself
adapted from https://github.com/LemuelPuglisi/turboprep), with the pipeline
logic kept as-is (it's the proven, working part) and wrapped into a
function so it can be called from the CLI or from Python instead of only
via `python turboprep-multiple-v2.py --inputs ... --outputs ...`.

Requires ANTs (`N4BiasFieldCorrection`, `antsRegistrationSyNQuick.sh`) and
FreeSurfer (`mri_synthstrip`, `mri_synthseg`) on PATH.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import nibabel as nib
import numpy as np
from intensity_normalization.normalize.whitestripe import WhiteStripeNormalize
from intensity_normalization.typing import Modality
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def run_turboprep(
    inputs: list[str],
    outputs: list[str],
    template: str,
    modality: str = "t1",
    threads: int = 1,
    shrink_factor: int = 3,
    registration_type: str = "a",
    no_bfc: set[str] | None = None,
    keep_intermediate: bool = False,
) -> None:
    """Run the turboprep pipeline over paired input/output paths.

    `outputs` are directories: each will contain corrected.nii.gz,
    segm.nii.gz, mask.nii.gz, normalized.nii.gz, brain.nii.gz (intermediate
    files removed unless `keep_intermediate`).
    """
    no_bfc = no_bfc or set()
    assert os.path.exists(template), f"{template} template image file doesn't exist"
    assert len(inputs) == len(outputs), "inputs and outputs must have the same length"

    outputs_dict = {}
    for input_path, output_path in tqdm(zip(inputs, outputs), total=len(inputs), desc="indexing"):
        if not os.path.exists(input_path):
            print("file", input_path, "does not exist.")
            continue

        outputs_dict[input_path] = {
            "bias_field_correction": os.path.join(output_path, "corrected.nii.gz"),
            "skull_stripping": os.path.join(output_path, "skullstrip.nii.gz"),
            "ants_prefix": os.path.join(output_path, "turboprep_"),
            "affine_registration": os.path.join(output_path, "turboprep_Warped.nii.gz"),
            "semantic_segmentation": os.path.join(output_path, "segm.nii.gz"),
            "brain_mask_extraction": os.path.join(output_path, "mask.nii.gz"),
            "intensity_normalization": os.path.join(output_path, "normalized.nii.gz"),
            "brain_extraction": os.path.join(output_path, "brain.nii.gz"),
        }
        if input_path in no_bfc:
            outputs_dict[input_path]["bias_field_correction"] = input_path

    if not outputs_dict:
        print("Nothing to process.")
        return

    # ------------------------------------------------------------------
    # Bias-field correction + skull stripping + registration to template
    # ------------------------------------------------------------------
    logging.info("Bias-field correction + skull stripping + registration to template")

    for input_path in tqdm(list(outputs_dict.keys()), desc="bfc/strip/register"):
        d = outputs_dict[input_path]
        corrected_path = d["bias_field_correction"]
        skullstrip_path = d["skull_stripping"]
        registered_path = d["affine_registration"]
        registered_pref = d["ants_prefix"]
        brain_path = d["brain_extraction"]

        if os.path.exists(registered_path) or os.path.exists(brain_path):
            continue

        os.makedirs(os.path.dirname(brain_path), exist_ok=True)

        if not (
            os.path.exists(corrected_path)
            or os.path.exists(skullstrip_path)
            or os.path.exists(registered_path)
        ):
            if input_path != corrected_path:
                subprocess.run(
                    [
                        "N4BiasFieldCorrection", "-d", "3",
                        "-i", input_path, "-o", corrected_path,
                        "-s", str(shrink_factor), "-v",
                    ],
                    stdout=open(os.path.join(os.path.dirname(corrected_path), "n4log.txt"), "w"),
                    stderr=subprocess.STDOUT,
                )

        if not os.path.exists(corrected_path):
            print("N4 correction has failed for", input_path)
            del outputs_dict[input_path]
            continue

        if not os.path.exists(skullstrip_path) and not os.path.exists(registered_path):
            subprocess.run(
                ["mri_synthstrip", "-i", corrected_path, "-o", skullstrip_path],
                stdout=open(os.path.join(os.path.dirname(skullstrip_path), "synthstriplog.txt"), "w"),
                stderr=subprocess.STDOUT,
            )

        if not os.path.exists(skullstrip_path):
            print("SynthStrip has failed for", input_path)
            del outputs_dict[input_path]
            continue

        if not os.path.exists(registered_path):
            subprocess.run(
                [
                    "antsRegistrationSyNQuick.sh", "-d", "3",
                    "-f", template, "-m", skullstrip_path,
                    "-o", registered_pref, "-n", str(threads),
                    "-t", registration_type,
                ],
                stdout=open(os.path.join(os.path.dirname(registered_pref), "antsreglog.txt"), "w"),
                stderr=subprocess.STDOUT,
            )

        if not os.path.exists(registered_path):
            print("Affine registration has failed for", input_path)
            del outputs_dict[input_path]
            continue

        if not keep_intermediate:
            if os.path.exists(skullstrip_path):
                os.remove(skullstrip_path)
            inv_warped = registered_pref + "InverseWarped.nii.gz"
            if os.path.exists(inv_warped):
                os.remove(inv_warped)
            if corrected_path != input_path and os.path.exists(corrected_path):
                os.remove(corrected_path)

        src = registered_pref + "0GenericAffine.mat"
        dst = os.path.join(os.path.dirname(registered_pref), "affine_transf.mat")
        if os.path.exists(src):
            if not os.path.exists(dst):
                os.replace(src, dst)
            else:
                os.remove(src)

    # ------------------------------------------------------------------
    # Semantic segmentation with SynthSeg
    # ------------------------------------------------------------------
    logging.info("Semantic segmentation using SynthSeg")

    reg_seg_pairs = [
        (d["affine_registration"], d["semantic_segmentation"])
        for d in outputs_dict.values()
        if not os.path.exists(d["semantic_segmentation"])
    ]

    if reg_seg_pairs:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        pid = os.getpid()
        temp_input = f"temp-input-{ts}-{pid}.txt"
        temp_output = f"temp-output-{ts}-{pid}.txt"

        with open(temp_input, "w") as f:
            f.writelines(reg + "\n" for reg, _ in reg_seg_pairs)
        with open(temp_output, "w") as f:
            f.writelines(seg + "\n" for _, seg in reg_seg_pairs)

        qc_output_path = os.path.join(os.path.dirname(reg_seg_pairs[0][1]), "synthseg_qc.csv")
        subprocess.run(
            [
                "mri_synthseg", "--i", temp_input, "--o", temp_output,
                "--fast", "--threads", str(threads), "--cpu", "--qc", qc_output_path,
            ],
            stdout=open(os.path.join(os.path.dirname(reg_seg_pairs[0][1]), "synthseglog.txt"), "w"),
            stderr=subprocess.STDOUT,
        )

        for tmp in (temp_input, temp_output):
            if os.path.exists(tmp):
                os.remove(tmp)

    for input_path in list(outputs_dict):
        if not os.path.exists(outputs_dict[input_path]["semantic_segmentation"]):
            print("failed segmentation on", input_path)
            del outputs_dict[input_path]

    # ------------------------------------------------------------------
    # Brain extraction and intensity normalization
    # ------------------------------------------------------------------
    def mask_and_normalize(paths):
        reg_path, seg_path = paths
        output_dir = os.path.dirname(seg_path)
        mask_path = os.path.join(output_dir, "mask.nii.gz")
        norm_path = os.path.join(output_dir, "normalized.nii.gz")
        brain_path = os.path.join(output_dir, "brain.nii.gz")

        if os.path.exists(mask_path) and os.path.exists(norm_path) and os.path.exists(brain_path):
            return

        try:
            reg = nib.load(reg_path)
            seg = nib.load(seg_path)
            reg_arr = reg.get_fdata()
        except Exception as e:
            print("loading failed for", reg_path, "with error", e)
            return

        mask_arr = None
        if not os.path.exists(mask_path):
            try:
                mask_arr = (seg.get_fdata().round() > 0).astype(np.uint8)
                nib.Nifti1Image(mask_arr, seg.affine, seg.header).to_filename(mask_path)
            except Exception as e:
                print("mask extraction failed for", reg_path, "with error", e)
                return
        else:
            mask_arr = nib.load(mask_path).get_fdata().astype(np.uint8)

        normalized_arr = None
        if not os.path.exists(norm_path):
            try:
                ws_norm = WhiteStripeNormalize()
                normalized_arr = ws_norm(reg_arr, mask_arr, modality=Modality.from_string(modality))
                nib.Nifti1Image(normalized_arr, reg.affine, reg.header).to_filename(norm_path)
            except Exception as e:
                print("normalization failed for", reg_path, "with error", e)
                return
        else:
            normalized_arr = nib.load(norm_path).get_fdata()

        if not os.path.exists(brain_path):
            try:
                brain_arr = normalized_arr.copy()
                brain_arr[mask_arr == 0.0] = brain_arr.min()
                nib.Nifti1Image(brain_arr, reg.affine, reg.header).to_filename(brain_path)
            except Exception as e:
                print("brain extraction failed for", reg_path, "with error", e)
                return

        if os.path.exists(reg_path):
            os.remove(reg_path)

    reg_seg_pairs = [
        (d["affine_registration"], d["semantic_segmentation"]) for d in outputs_dict.values()
    ]

    with Pool(processes=threads) as pool:
        for _ in tqdm(
            pool.imap_unordered(mask_and_normalize, reg_seg_pairs),
            total=len(reg_seg_pairs),
            desc="mask+normalize",
        ):
            pass

    print("turboprep finished.")


def _read_lines(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def main(argv: list[str] | None = None) -> None:
    """CLI entry point kept for parity with the legacy script (called from
    PBS jobs via `--inputs file.txt --outputs file.txt`)."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True, help="text file, one input image path per line")
    parser.add_argument("--outputs", required=True, help="text file, one output dir per line")
    parser.add_argument("--template", required=True, help="path of template image")
    parser.add_argument("-m", "--modality", default="t1")
    parser.add_argument("-t", "--threads", type=int, default=int(os.environ.get("PBS_NP") or 1))
    parser.add_argument("-s", "--shrink-factor", type=int, default=3)
    parser.add_argument("-r", "--registration-type", default="a")
    parser.add_argument("--no-bfc", help="text file listing inputs for which to skip bias field correction")
    parser.add_argument("--keep", action="store_true", help="keep intermediate files")
    args = parser.parse_args(argv)

    no_bfc = set(_read_lines(args.no_bfc)) if args.no_bfc else set()

    run_turboprep(
        inputs=_read_lines(args.inputs),
        outputs=_read_lines(args.outputs),
        template=args.template,
        modality=args.modality,
        threads=args.threads,
        shrink_factor=args.shrink_factor,
        registration_type=args.registration_type,
        no_bfc=no_bfc,
        keep_intermediate=args.keep,
    )


if __name__ == "__main__":
    main()
