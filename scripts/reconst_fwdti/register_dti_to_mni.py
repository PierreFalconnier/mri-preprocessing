"""Register full-volume DTI maps to MNI through the associated T1w image.

The transform chain is DWI (mean b=0) -> skull-stripped T1w -> MNI.  It uses
SynthStrip and ANTs from the already-installed ``lemuelpuglisi/turboprep``
Docker image, avoiding a host-level FreeSurfer/ANTs installation.
"""

import argparse
import os
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DWI_DIR = Path(
    "/run/media/falconnier/bb9ecfb7-b58f-41e9-a37d-fda12951eb4e/"
    "PPMI_anat_dwi_BIDS/sub-55984/ses-20211210/dwi"
)
DEFAULT_T1 = Path(
    "/run/media/falconnier/bb9ecfb7-b58f-41e9-a37d-fda12951eb4e/"
    "PPMI_anat_dwi_BIDS/sub-55984/ses-20211210/anat/"
    "sub-55984_ses-20211210_acq-SAGITTAL3D_run-01_T1w.nii.gz"
)
DEFAULT_TEMPLATE = (
    PROJECT_ROOT / "preprocessing/MNI_templates/MNI152_T1_1mm_brain_RAS.nii.gz"
)
DEFAULT_DTI_OUTPUT = Path(__file__).parent / "outputs"
IMAGE = "lemuelpuglisi/turboprep:latest"


def run_container(mounts, entrypoint, arguments, log_path):
    command = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}"]
    for host_path, container_path, read_only in mounts:
        suffix = ":ro" if read_only else ""
        command += ["-v", f"{host_path}:{container_path}{suffix}"]
    command += ["--entrypoint", entrypoint, IMAGE, *arguments]
    print("+", " ".join(command))
    with log_path.open("w") as log_file:
        subprocess.run(command, check=True, stdout=log_file, stderr=subprocess.STDOUT)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--dwi-dir", type=Path, default=DEFAULT_DWI_DIR)
parser.add_argument("--t1", type=Path, default=DEFAULT_T1)
parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
parser.add_argument("--dti-output", type=Path, default=DEFAULT_DTI_OUTPUT)
parser.add_argument(
    "--output-dir", type=Path, default=DEFAULT_DTI_OUTPUT / "mni_affine"
)
parser.add_argument("--threads", type=int, default=8)
args = parser.parse_args()

for path in (args.dwi_dir, args.t1, args.template, args.dti_output):
    if not path.exists():
        raise FileNotFoundError(path)
for name in ("brain_mask_auto.nii.gz", "dti_fa.nii.gz", "dti_md.nii.gz"):
    if not (args.dti_output / name).exists():
        raise FileNotFoundError(
            f"Run reconst_fwdti.py first; missing {args.dti_output / name}"
        )

args.output_dir.mkdir(parents=True, exist_ok=True)
dwi_files = sorted(args.dwi_dir.glob("*.nii")) + sorted(args.dwi_dir.glob("*.nii.gz"))
if len(dwi_files) != 1:
    raise FileNotFoundError(
        f"Expected one DWI NIfTI in {args.dwi_dir}; found {len(dwi_files)}."
    )

# Mean b=0, restricted to the automatically estimated DWI brain mask, is a
# much better DWI-to-T1 registration target than an arbitrary diffusion volume.
bvals = np.loadtxt(next(args.dwi_dir.glob("*.bval"))).reshape(-1)
dwi_img = nib.load(dwi_files[0])
b0_idx = np.flatnonzero(bvals <= 50)
if not len(b0_idx):
    raise ValueError("No b=0 volumes were found.")
dwi_data = np.asarray(dwi_img.dataobj, dtype=np.float32)
mask = np.asarray(
    nib.load(args.dti_output / "brain_mask_auto.nii.gz").dataobj, dtype=bool
)
b0_mean = dwi_data[..., b0_idx].mean(axis=-1) * mask
b0_path = args.output_dir / "dwi_b0_mean_brain.nii.gz"
nib.save(
    nib.Nifti1Image(b0_mean.astype(np.float32), dwi_img.affine, dwi_img.header), b0_path
)

# Bind only the input subject directory and project tree. Container paths make
# the commands portable despite spaces or special characters in host paths.
subject_dir = args.t1.parent.parent
mounts = [
    (subject_dir, "/subject", True),
    (PROJECT_ROOT, "/project", False),
]
t1_container = "/subject/anat/" + args.t1.name
template_container = "/project/" + str(args.template.relative_to(PROJECT_ROOT))
output_container = "/project/" + str(args.output_dir.relative_to(PROJECT_ROOT))

t1_brain = args.output_dir / "t1w_synthstrip_brain.nii.gz"
t1_mask = args.output_dir / "t1w_synthstrip_mask.nii.gz"
run_container(
    mounts,
    "/opt/freesurfer-7.4.1/bin/mri_synthstrip",
    [
        "-i",
        t1_container,
        "-o",
        f"{output_container}/{t1_brain.name}",
        "-m",
        f"{output_container}/{t1_mask.name}",
    ],
    args.output_dir / "synthstrip.log",
)

# ANTs matrices map moving -> fixed.  Register the b=0 image to the stripped
# T1, then T1 to the supplied brain-only MNI reference.
dwi_to_t1_prefix = args.output_dir / "dwi_b0_to_t1_"
t1_to_mni_prefix = args.output_dir / "t1_to_mni_"
ants_quick = "/opt/ants-2.4.3/antsRegistrationSyNQuick.sh"
run_container(
    mounts,
    ants_quick,
    [
        "-d",
        "3",
        "-t",
        "a",
        "-n",
        str(args.threads),
        "-f",
        f"{output_container}/{t1_brain.name}",
        "-m",
        f"{output_container}/{b0_path.name}",
        "-o",
        f"{output_container}/{dwi_to_t1_prefix.name}",
    ],
    args.output_dir / "dwi_to_t1_ants.log",
)
run_container(
    mounts,
    ants_quick,
    [
        "-d",
        "3",
        "-t",
        "a",
        "-n",
        str(args.threads),
        "-f",
        template_container,
        "-m",
        f"{output_container}/{t1_brain.name}",
        "-o",
        f"{output_container}/{t1_to_mni_prefix.name}",
    ],
    args.output_dir / "t1_to_mni_ants.log",
)

dwi_to_t1_affine = dwi_to_t1_prefix.with_name(
    dwi_to_t1_prefix.name + "0GenericAffine.mat"
)
t1_to_mni_affine = t1_to_mni_prefix.with_name(
    t1_to_mni_prefix.name + "0GenericAffine.mat"
)
for transform in (dwi_to_t1_affine, t1_to_mni_affine):
    if not transform.exists():
        raise RuntimeError(f"ANTs did not create expected transform: {transform}")

ants_apply = "/opt/ants-2.4.3/antsApplyTransforms"
for source_name, output_name, interpolation in (
    ("dti_fa.nii.gz", "dti_fa_mni_affine.nii.gz", "Linear"),
    ("dti_md.nii.gz", "dti_md_mni_affine.nii.gz", "Linear"),
    ("brain_mask_auto.nii.gz", "dwi_brain_mask_mni_affine.nii.gz", "NearestNeighbor"),
):
    run_container(
        mounts,
        ants_apply,
        [
            "-d",
            "3",
            "-i",
            f"/project/{(args.dti_output / source_name).relative_to(PROJECT_ROOT)}",
            "-r",
            template_container,
            "-o",
            f"{output_container}/{output_name}",
            "-n",
            interpolation,
            # ANTs applies transforms right-to-left: DWI->T1 first, then T1->MNI.
            "-t",
            f"{output_container}/{t1_to_mni_affine.name}",
            "-t",
            f"{output_container}/{dwi_to_t1_affine.name}",
        ],
        args.output_dir / f"apply_{output_name}.log",
    )

print(f"Completed affine DWI-to-MNI workflow. Outputs: {args.output_dir}")
