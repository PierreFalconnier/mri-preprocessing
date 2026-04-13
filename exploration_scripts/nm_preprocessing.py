"""
IMPORTANT:
Run this script from a BASH terminal (NOT fish):

    bash -lc "python nm_preprocessing.py"
"""

import glob
import os
import subprocess

import nibabel as nib
from nilearn.image import mean_img, smooth_img

# =========================
# CONFIG
# =========================
data_dir = "/run/media/falconnier/bb9ecfb7-b58f-41e9-a37d-fda12951eb4e/PPMI_anat_dwi_BIDS/sub-408632/ses-20241113/anat/"
output_dir = "/home/falconnier/Documents/mri-preprocessing/derivatives_nm"
os.makedirs(output_dir, exist_ok=True)

subject = "sub-408632"
session = "ses-20241113"


# =========================
# HELPER (bash-safe execution)
# =========================
def run(cmd):
    """Run command in bash (important for ANTs scripts)."""
    subprocess.run(cmd, shell=True, executable="/bin/bash", check=True)


# =========================
# STEP 1: LOAD NM RUNS
# =========================
nm_files = sorted(
    glob.glob(os.path.join(data_dir, f"{subject}_{session}_acq-NM_run-*.nii.gz"))
)

print("Found NM runs:", nm_files)

nm_imgs = [nib.load(f) for f in nm_files]

# =========================
# STEP 2: REGISTER EACH NM TO T1 (later step depends on T1)
# =========================
t1_file = glob.glob(
    os.path.join(data_dir, f"{subject}_{session}_acq-SAGITTAL3D*_T1w.nii.gz")
)[0]

print("T1 file:", t1_file)

nm_to_t1_prefixes = []

nm_to_t1_imgs = []

for i, nm_path in enumerate(nm_files):
    prefix = os.path.join(output_dir, f"nm{i}_to_t1_")
    nm_to_t1_prefixes.append(prefix)

    run(f"""
    antsRegistrationSyNQuick.sh \
    -d 3 \
    -f {t1_file} \
    -m {nm_path} \
    -o {prefix}
    """)

    warped = prefix + "Warped.nii.gz"
    nm_to_t1_imgs.append(nib.load(warped))

# =========================
# STEP 3: COMPUTE MEAN NM (in T1 space)
# =========================
nm_mean = mean_img(nm_to_t1_imgs)

nm_mean_file = os.path.join(output_dir, "nm_mean_in_t1.nii.gz")
nm_mean.to_filename(nm_mean_file)

print("NM mean (T1 space) saved")

# =========================
# STEP 4: REGISTER T1 → MNI
# =========================
mni_template = "/home/falconnier/fsl/data/standard/MNI152_T1_1mm.nii.gz"

t1_to_mni_prefix = os.path.join(output_dir, "t1_to_mni_")

run(f"""
antsRegistrationSyNQuick.sh \
-d 3 \
-f {mni_template} \
-m {t1_file} \
-o {t1_to_mni_prefix}
""")

# =========================
# STEP 5: APPLY TRANSFORM TO MEAN NM
# =========================
nm_mni = os.path.join(output_dir, "nm_mean_in_mni.nii.gz")

run(f"""
antsApplyTransforms \
-d 3 \
-i {nm_mean_file} \
-r {mni_template} \
-o {nm_mni} \
-t {t1_to_mni_prefix}1Warp.nii.gz \
-t {t1_to_mni_prefix}0GenericAffine.mat
""")

# =========================
# STEP 6: SMOOTHING (optional)
# =========================
smoothed = smooth_img(nm_mni, fwhm=2)
smoothed_file = os.path.join(output_dir, "nm_mean_in_mni_smooth.nii.gz")
smoothed.to_filename(smoothed_file)

print("Preprocessing complete!")
