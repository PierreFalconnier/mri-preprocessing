# script adapted from https://github.com/LemuelPuglisi/turboprep/blob/main/turboprep-multiple.py

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from multiprocessing import Pool

import nibabel as nib
import numpy as np
from intensity_normalization.normalize.whitestripe import WhiteStripeNormalize
from intensity_normalization.typing import Modality
from tqdm import tqdm


def preprocess_one(args):
    (
        input_path,
        input_outputs,
        template,
        shrinkf,
        regtype,
        keepint,
    ) = args

    corrected_path = input_outputs["bias_field_correction"]
    skullstrip_path = input_outputs["skull_stripping"]
    registered_path = input_outputs["affine_registration"]
    registered_pref = input_outputs["ants_prefix"]
    brain_path = input_outputs["brain_extraction"]

    try:
        # Skip if already processed
        if os.path.exists(registered_path) or os.path.exists(brain_path):
            return input_path, True

        os.makedirs(os.path.dirname(brain_path), exist_ok=True)

        # ---------------- N4 ----------------
        if input_path != corrected_path:
            subprocess.run(
                [
                    "N4BiasFieldCorrection",
                    "-d",
                    "3",
                    "-i",
                    input_path,
                    "-o",
                    corrected_path,
                    "-s",
                    str(shrinkf),
                    "-v",
                ],
                check=True,
            )

        if not os.path.exists(corrected_path):
            return input_path, False

        # ---------------- SynthStrip ----------------
        log1 = os.path.join(os.path.dirname(skullstrip_path), "synthstriplog.txt")
        with open(log1, "w") as f:
            subprocess.run(
                ["mri_synthstrip", "-i", corrected_path, "-o", skullstrip_path],
                stdout=f,
                stderr=subprocess.STDOUT,
                check=True,
            )

        # ---------------- ANTs ----------------
        log2 = os.path.join(os.path.dirname(registered_pref), "antsreglog.txt")
        with open(log2, "w") as f:
            subprocess.run(
                [
                    "antsRegistrationSyNQuick.sh",
                    "-d",
                    "3",
                    "-f",
                    template,
                    "-m",
                    skullstrip_path,
                    "-o",
                    registered_pref,
                    "-n",
                    "1",  # since we are already parallelizing at the image level, we don't want ants to use multiple threads for a single image
                    "-t",
                    regtype,
                ],
                stdout=f,
                stderr=subprocess.STDOUT,
                check=True,
            )

        if not os.path.exists(registered_path):
            return input_path, False

        # ---------------- Cleanup ----------------
        if not keepint:
            if os.path.exists(skullstrip_path):
                os.remove(skullstrip_path)
            inv = registered_pref + "InverseWarped.nii.gz"
            if os.path.exists(inv):
                os.remove(inv)
            if corrected_path != input_path and os.path.exists(corrected_path):
                os.remove(corrected_path)

        os.rename(
            registered_pref + "0GenericAffine.mat",
            os.path.join(os.path.dirname(registered_pref), "affine_transf.mat"),
        )

        return input_path, True

    except Exception as e:
        print(f"Failed on {input_path}: {e}")
        return input_path, False


def mask_and_normalize(paths):
    reg_path, seg_path = paths
    output_dir = os.path.dirname(seg_path)
    mask_path = os.path.join(output_dir, "mask.nii.gz")
    norm_path = os.path.join(output_dir, "normalized.nii.gz")
    brain_path = os.path.join(output_dir, "brain.nii.gz")

    if (
        os.path.exists(mask_path)
        and os.path.exists(norm_path)
        and os.path.exists(brain_path)
    ):
        return

    try:
        reg = nib.load(reg_path)
        seg = nib.load(seg_path)
        reg_arr = reg.get_fdata()
    except Exception as e:
        print("loading failed for", reg_path, "with error", e)
        return

    if not os.path.exists(mask_path):
        try:
            mask_arr = (seg.get_fdata().round() > 0).astype(np.uint8)
            mask = nib.Nifti1Image(mask_arr, seg.affine, seg.header)
            mask.to_filename(mask_path)
        except Exception as e:
            print("brain extraction failed for", reg_path, "with error", e)
            return

    if not os.path.exists(norm_path):
        try:
            ws_norm = WhiteStripeNormalize()
            normalized_arr = ws_norm(
                reg_arr, mask_arr, modality=Modality.from_string(modality)
            )
            normalized = nib.Nifti1Image(normalized_arr, reg.affine, reg.header)
            normalized.to_filename(norm_path)
        except Exception as e:
            print("normalization failed for", reg_path, "with error", e)
            return

    if not os.path.exists(brain_path):
        try:
            # brain_arr = normalized_arr.copy()
            # brain_arr[mask_arr == 0.0] = brain_arr.min()
            brain_arr = normalized_arr
            brain_arr[mask_arr == 0] = brain_arr.min()
            brain = nib.Nifti1Image(brain_arr, reg.affine, reg.header)
            brain.to_filename(brain_path)
        except Exception as e:
            print("brain extraction failed for", reg_path, "with error", e)
            return

    if os.path.exists(reg_path):
        os.remove(reg_path)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

NPROC = int(os.cpu_count())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--inputs",
        type=str,
        required=True,
        help="text file where each line is the path of an image to process",
    )
    parser.add_argument(
        "--outputs",
        type=str,
        required=True,
        help="text file where each line is the path to an output",
    )
    parser.add_argument(
        "--template", type=str, required=True, help="path of template image"
    )
    parser.add_argument(
        "-m",
        "--modality",
        type=str,
        default="t1",
        help="Modality {t2,other,md,t1,pd,flair} (default is t1)",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=NPROC,
        help="Threads (default: number of cores)",
    )
    parser.add_argument(
        "-s",
        "--shrink-factor",
        type=int,
        default=3,
        help="Bias field correction shrink factor (default: 3), see N4BiasFieldCorrection",
    )
    parser.add_argument(
        "-r",
        "--registration-type",
        type=str,
        default="a",
        help="Registration type {t,r,a} (default is 'a' (affine), see antsRegistrationSyNQuick.sh)",
    )
    parser.add_argument(
        "--no-bfc",
        type=str,
        help="text file listing the inputs for which to skip bias field correction",
    )
    parser.add_argument("--keep", action="store_true", help="Keep intermediate files")

    args = parser.parse_args()
    inp_file = args.inputs
    out_file = args.outputs
    nbc_file = args.no_bfc
    template = args.template

    modality = args.modality
    threads = args.threads
    shrinkf = args.shrink_factor
    regtype = args.registration_type
    keepint = args.keep

    assert os.path.exists(inp_file), f"{inp_file} input file doesn't exist"
    assert os.path.exists(out_file), f"{out_file} output file doesn't exist"
    assert os.path.exists(template), f"{template} template image file doesn't exist"
    assert nbc_file is None or os.path.exists(nbc_file), (
        f"{nbc_file} no-bfc file doesn't exist"
    )

    print("🚀 reading input files")

    with open(inp_file, "r") as f:
        inp_list = [line.strip() for line in f.readlines()]

    with open(out_file, "r") as f:
        out_list = [line.strip() for line in f.readlines()]

    nbc_list = set()
    if nbc_file is not None:
        with open(nbc_file, "r") as f:
            nbc_list = set([line.strip() for line in f.readlines()])

    print("🚀 creating output dictionary")

    outputs_dict = {}
    for input_path, output_path in tqdm(zip(inp_list, out_list), total=len(inp_list)):
        if not os.path.exists(input_path):
            print("file", input_path, "does not exists.")
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

        if input_path in nbc_list:
            outputs_dict[input_path]["bias_field_correction"] = input_path

    print(len(outputs_dict))
    print(outputs_dict[list(outputs_dict.keys())[0]])

    #######################################################################
    # Bias-field correction + skull stripping + registration to template  #
    #######################################################################

    print("🚀 Bias-field correction + skull stripping + registration to template")
    logging.info(
        "loginfo : 🚀 Bias-field correction + skull stripping + registration to template"
    )

    tasks = [
        (
            input_path,
            outputs_dict[input_path],
            template,
            shrinkf,
            regtype,
            keepint,
        )
        for input_path in outputs_dict.keys()
    ]

    successful = {}

    with Pool(processes=min(threads, 4)) as pool:
        for input_path, ok in tqdm(
            pool.imap_unordered(preprocess_one, tasks),
            total=len(tasks),
        ):
            successful[input_path] = ok

    # Remove failed ones
    outputs_dict = {k: v for k, v in outputs_dict.items() if successful.get(k, False)}

    #######################################################
    # Semantic segmentation with SynthSeg                 #
    #######################################################

    print("🚀 semantic segmentation using SynthSeg")

    reg_seg_pairs = []
    for input_path, input_dict in outputs_dict.items():
        reg_path = input_dict["affine_registration"]
        seg_path = input_dict["semantic_segmentation"]
        if not os.path.exists(seg_path):
            reg_seg_pairs.append((reg_path, seg_path))

    if len(reg_seg_pairs) > 0:
        # create unique temp filenames to avoid collisions when multiple jobs run
        ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        pid = os.getpid()
        temp_input = f"temp-input-{ts}-{pid}.txt"
        temp_output = f"temp-output-{ts}-{pid}.txt"

        if os.path.exists(temp_input):
            os.remove(temp_input)
        if os.path.exists(temp_output):
            os.remove(temp_output)

        with open(temp_input, "w") as f:
            for reg, _ in reg_seg_pairs:
                f.write(reg + "\n")

        with open(temp_output, "w") as f:
            for _, seg in reg_seg_pairs:
                f.write(seg + "\n")

        subprocess.run(
            [
                "mri_synthseg",
                "--i",
                temp_input,
                "--o",
                temp_output,
                "--fast",
                "--threads",
                str(threads),
                "--cpu",
            ],
            stdout=os.path.join(
                os.path.dirname(reg_seg_pairs[0][1]), "synthseglog.txt"
            ),
            stderr=subprocess.STDOUT,
            check=True,
        )

        if os.path.exists(temp_input):
            os.remove(temp_input)
        if os.path.exists(temp_output):
            os.remove(temp_output)

    for input_path in list(outputs_dict):
        segm_path = outputs_dict[input_path]["semantic_segmentation"]
        if not os.path.exists(segm_path):
            print("failed segmentation on", input_path)
            del outputs_dict[input_path]

    #######################################################
    # Brain extraction and intensity normalization         #
    #######################################################

    print("🚀 computing brain mask, intensity normalization and skull stripping")

    reg_seg_pairs = [
        (d["affine_registration"], d["semantic_segmentation"])
        for d in outputs_dict.values()
    ]

    pool = Pool(processes=threads)
    for _ in tqdm(
        pool.imap_unordered(mask_and_normalize, reg_seg_pairs), total=len(reg_seg_pairs)
    ):
        pass

    print("🚀 finish.")
