# script adapted from https://github.com/LemuelPuglisi/turboprep/blob/main/turboprep-multiple.py

import argparse
import os

from tqdm import tqdm

# NPROC = int(os.environ.get("PBS_NP") or os.cpu_count() or 1)
# NPROC = int(os.cpu_count())
NPROC = 1

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

    args = parser.parse_args()
    inp_file = args.inputs
    out_file = args.outputs
    template = args.template

    assert os.path.exists(inp_file), f"{inp_file} input file doesn't exist"
    assert os.path.exists(out_file), f"{out_file} output file doesn't exist"
    assert os.path.exists(template), f"{template} template image file doesn't exist"

    print("🚀 reading input files")

    with open(inp_file, "r") as f:
        inp_list = [line.strip() for line in f.readlines()]

    with open(out_file, "r") as f:
        out_list = [line.strip() for line in f.readlines()]

    print("🚀 creating output dictionary")

    outputs_dict = {}
    for input_path, output_path in tqdm(zip(inp_list, out_list), total=len(inp_list)):
        if not os.path.exists(input_path):
            print("file", input_path, "does not exists.")
            continue

        outputs_dict[input_path] = {
            "semantic_segmentation": os.path.join(output_path, "segm.nii.gz"),
            "brain_mask_extraction": os.path.join(output_path, "mask.nii.gz"),
            "intensity_normalization": os.path.join(output_path, "normalized.nii.gz"),
            "brain_extraction": os.path.join(output_path, "brain.nii.gz"),
        }

    print(len(outputs_dict))
    print(outputs_dict[list(outputs_dict.keys())[0]])

    # compute stats
    # pool = Pool(processes=NPROC)
