"""
Run from BASH (NOT fish):

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
output_dir = (
    "/home/falconnier/Documents/mri-preprocessing/exploration_scripts/derivatives_nm"
)
os.makedirs(output_dir, exist_ok=True)

subject = "sub-408632"
session = "ses-20241113"

mni_template = "/home/falconnier/fsl/data/standard/MNI152_T1_1mm_brain.nii.gz"


# =========================
# RUN COMMANDS IN BASH
# =========================
def run(cmd):
    subprocess.run(cmd, shell=True, executable="/bin/bash", check=True)


# =========================
# STEP 1: LOAD NM RUNS
# =========================
nm_files = sorted(
    glob.glob(os.path.join(data_dir, f"{subject}_{session}_acq-NM_run-*.nii.gz"))
)

print("Found NM runs:", nm_files)

t1_file = glob.glob(
    os.path.join(data_dir, f"{subject}_{session}_acq-SAGITTAL3D*_T1w.nii.gz")
)[0]

print("T1 file:", t1_file)

# =========================
# STEP 2: MEAN NM (IN NATIVE SPACE)
# =========================
nm_imgs = [nib.load(f) for f in nm_files]

nm_mean = mean_img(nm_imgs)

nm_mean_file = os.path.join(output_dir, "nm_mean_native.nii.gz")
nm_mean.to_filename(nm_mean_file)

print("Mean NM (native space) computed")

# =========================
# STEP 3: SYNTHSTRIP ON T1
# =========================
t1_brain = os.path.join(output_dir, "t1_brain.nii.gz")
t1_mask = os.path.join(output_dir, "t1_brain_mask.nii.gz")

run(f"""
mri_synthstrip \
-i {t1_file} \
-o {t1_brain} \
-m {t1_mask}
""")

# =========================
# STEP 4: REGISTER NM MEAN → T1
# =========================
nm_to_t1_prefix = os.path.join(output_dir, "nm_mean_to_t1_")

run(f"""
antsRegistrationSyNQuick.sh \
-d 3 \
-f {t1_file} \
-m {nm_mean_file} \
-o {nm_to_t1_prefix}
""")

nm_in_t1 = nm_to_t1_prefix + "Warped.nii.gz"

# =========================
# STEP 5: APPLY T1 MASK TO NM (IN T1 SPACE)
# =========================
nm_masked_t1 = os.path.join(output_dir, "nm_mean_t1_masked.nii.gz")

run(f"""
fslmaths {nm_in_t1} -mas {t1_mask} {nm_masked_t1}
""")

# =========================
# STEP 6: REGISTER T1 → MNI
# =========================
t1_to_mni_prefix = os.path.join(output_dir, "t1_to_mni_")

print(
    "SHOULD USE THE BRAIN EXTRACTED T1 FOR THIS STEP, BUT USING THE WHOLE T1 INSTEAD (CHECK IF IT WORKS)"
)
exit()

run(f"""
antsRegistrationSyNQuick.sh \
-d 3 \
-f {mni_template} \
-m {t1_file} \
-o {t1_to_mni_prefix}
""")

# =========================
# STEP 7: APPLY TRANSFORM TO NM
# =========================
nm_mni = os.path.join(output_dir, "nm_mean_mni.nii.gz")

run(f"""
antsApplyTransforms \
-d 3 \
-i {nm_masked_t1} \
-r {mni_template} \
-o {nm_mni} \
""")

# =========================
# STEP 8: SMOOTHING
# =========================
smoothed = smooth_img(nm_mni, fwhm=2)
smoothed.to_filename(os.path.join(output_dir, "nm_mean_mni_smooth.nii.gz"))

print("DONE ✔")
