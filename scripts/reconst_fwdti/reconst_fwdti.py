"""
=============================================================================
Using the free water elimination model to remove DTI free water contamination
=============================================================================

As shown previously (see
:ref:`sphx_glr_examples_built_reconstruction_reconst_dti.py`), the diffusion
tensor model is a simple way to characterize diffusion anisotropy. However,
in regions near the ventricles and parenchyma, anisotropy can be
underestimated by partial volume effects of the cerebral spinal fluid (CSF).
This free water contamination can particularly corrupt Diffusion Tensor
Imaging analysis of microstructural changes when different groups of subjects
show different brain morphology (e.g. brain ventricle enlargement associated
with brain tissue atrophy that occurs in several brain pathologies and aging).

A way to remove this free water influences is to expand the DTI model to take
into account an extra compartment representing the contributions of free water
diffusion :footcite:p:`Pasternak2009`. The expression of the expanded DTI model
is shown below:

.. math::

    S(\\mathbf{g}, b) = S_0(1-f)e^{-b\\mathbf{g}^T \\mathbf{D}
    \\mathbf{g}}+S_0fe^{-b D_{iso}}

where $\\mathbf{g}$ and $b$ are diffusion gradient direction and weighted (more
information see :ref:`sphx_glr_examples_built_reconstruction_reconst_dti.py`),
$S(\\mathbf{g}, b)$ is thebdiffusion-weighted signal measured, $S_0$ is the
signal in a measurement with no diffusion weighting, $\\mathbf{D}$ is the
diffusion tensor, $f$ the volume fraction of the free water component, and
$D_{iso}$ is the isotropic value of the free water diffusion (normally set to
$3.0 \times 10^{-3} mm^{2}s^{-1}$).

In this example, we show how to process a diffusion weighting dataset using an
adapted version of the free water elimination proposed by :footcite:p:`Hoy2014`.

The full details of Dipy's free water DTI implementation was published in
:footcite:p:`NetoHenriques2017`. Please cite this work if you use this
algorithm.

Let's start by importing the relevant modules:
"""

import argparse
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
from dipy.align import motion_correction
from dipy.core.gradients import gradient_table
from dipy.denoise.gibbs import gibbs_removal
from dipy.denoise.localpca import mppca
from dipy.reconst import dti, fwdti
from dipy.segment.mask import median_otsu

###############################################################################
# Without spatial constrains the free water elimination model cannot be solved
# in data acquired from one non-zero b-value :footcite:p:`Hoy2014`. Therefore,
# here we download a dataset that was acquired with multiple b-values.

# data_path = fetch_hbn(["NDARAA948VFH"])[1]
# dwi_path = (
#     data_path / "derivatives" / "qsiprep" / "sub-NDARAA948VFH" / "ses-HBNsiteRU" / "dwi"
# )

# img = nib.load(
#     dwi_path
#     / "sub-NDARAA948VFH_ses-HBNsiteRU_acq-64dir_space-T1w_desc-preproc_dwi.nii.gz"
# )

# gtab = gradient_table(
#     dwi_path
#     / "sub-NDARAA948VFH_ses-HBNsiteRU_acq-64dir_space-T1w_desc-preproc_dwi.bval",
#     bvecs=(
#         dwi_path
#         / "sub-NDARAA948VFH_ses-HBNsiteRU_acq-64dir_space-T1w_desc-preproc_dwi.bvec"
#     ),
# )

parser = argparse.ArgumentParser(
    description="Fit DTI and, for multi-shell acquisitions, free-water DTI."
)
parser.add_argument(
    "dwi_path",
    nargs="?",
    type=Path,
    default=Path(
        "/run/media/falconnier/bb9ecfb7-b58f-41e9-a37d-fda12951eb4e/"
        "PPMI_anat_dwi_BIDS/sub-55984/ses-20211210/dwi"
    ),
    help="Directory containing one DWI NIfTI, .bval, and .bvec file.",
)
parser.add_argument("--slice", dest="slice_index", type=int, default=50)
parser.add_argument(
    "--output-dir",
    type=Path,
    default=Path(__file__).parent / "outputs",
    help="Directory for the estimated mask, DTI maps, tensor image, and preview figures.",
)
args = parser.parse_args()

dwi_files = sorted(args.dwi_path.glob("*.nii")) + sorted(args.dwi_path.glob("*.nii.gz"))
bval_files = sorted(args.dwi_path.glob("*.bval"))
bvec_files = sorted(args.dwi_path.glob("*.bvec"))
if len(dwi_files) != 1 or len(bval_files) != 1 or len(bvec_files) != 1:
    raise FileNotFoundError(
        "Expected exactly one .nii/.nii.gz, .bval, and .bvec file in "
        f"{args.dwi_path}; found {len(dwi_files)}, {len(bval_files)}, and {len(bvec_files)}."
    )

img = nib.load(dwi_files[0])
gtab = gradient_table(bval_files[0], bvecs=bvec_files[0])
data = np.asarray(img.dataobj, dtype=np.float32)

if data.ndim != 4 or data.shape[-1] != len(gtab.bvals):
    raise ValueError(
        f"DWI must be X x Y x Z x N with one gradient per volume; got {data.shape} "
        f"and {len(gtab.bvals)} gradients."
    )
if not np.any(gtab.b0s_mask):
    raise ValueError(
        "No b=0 volumes were found; a b=0 image is required to estimate a mask."
    )

args.output_dir.mkdir(parents=True, exist_ok=True)

# print shapes and basic info
print(f"DWI shape: {data.shape}; b-values: {np.unique(gtab.bvals)}")
# print gtab info
print(f"Gradient table: {gtab}")
# print number of b=0 volumes
print(f"Number of b=0 volumes: {np.sum(gtab.b0s_mask)}")

###############################################################################
# Denoise the raw DWI signal before fitting any tensor model. MP-PCA exploits
# redundancy across diffusion volumes within local patches to separate signal
# from noise and estimates the noise level automatically, so no manual sigma
# is required.
data, sigma = mppca(data, patch_radius=2, return_sigma=True)
print(f"Denoised with MP-PCA; median estimated noise sigma: {np.median(sigma):.4g}")

###############################################################################
# Remove Gibbs (truncation) ringing artefacts, which appear as spurious
# oscillations near sharp intensity edges (e.g. CSF/tissue boundaries) due to
# finite k-space sampling. Applied after denoising, on the volume axis.
data = gibbs_removal(data, slice_axis=2, num_processes=-1)
print("Applied Gibbs ringing removal.")

###############################################################################
# Correct for subject motion by registering each volume to the b0 reference
# (progressively through center-of-mass, translation, rigid, and affine
# transforms). This does not correct for eddy-current-induced distortions,
# which require a dedicated tool (e.g. FSL eddy).
reg_img, reg_affines = motion_correction(data, gtab, img.affine)
data = np.asarray(reg_img.get_fdata(), dtype=np.float32)
print("Applied motion correction.")


###############################################################################
# The free water DTI model can take some minutes to process the full data set.
# Estimate a brain mask from the b=0 images instead of requiring a separate
# pre-processing mask. ``median_otsu`` returns the masked DWI and a 3-D bool
# mask in the native DWI grid.
b0_idx = np.flatnonzero(gtab.b0s_mask)
_, mask = median_otsu(data, vol_idx=b0_idx, median_radius=2, numpass=1, dilate=1)
mask = mask.astype(bool, copy=False)
if not mask.any():
    raise RuntimeError("Automatic mask estimation produced an empty mask.")
nib.save(
    nib.Nifti1Image(mask.astype(np.uint8), img.affine, img.header),
    args.output_dir / "brain_mask_auto.nii.gz",
)
print(f"DWI shape: {data.shape}; estimated mask: {mask.sum()} voxels")

###############################################################################
# The fit below is performed over the entire 3-D volume. ``slice_index`` is
# used only to select a slice for the preview figures.

if not 0 <= args.slice_index < data.shape[2]:
    raise ValueError(f"--slice must be between 0 and {data.shape[2] - 1}.")
if not mask[:, :, args.slice_index].any():
    raise RuntimeError(
        f"The estimated mask has no voxels in slice {args.slice_index}; choose another --slice."
    )

###############################################################################
# The free water elimination model fit can then be initialized by instantiating
# a FreeWaterTensorModel class object:
# but multishell is needed to fit the free water elimination model. We check if the data has at least two non-zero b-value shells before fitting the model.

nonzero_shells = np.unique(np.round(gtab.bvals[~gtab.b0s_mask], decimals=0))
can_fit_fwdti = len(nonzero_shells) >= 2
if can_fit_fwdti:
    fwdtimodel = fwdti.FreeWaterTensorModel(gtab)
else:
    print(
        "Skipping free-water DTI: only one non-zero b-value shell is present "
        f"({nonzero_shells.tolist()})."
    )
    warnings.warn(
        "Skipping free-water DTI: this acquisition has only one non-zero b-value "
        f"shell ({nonzero_shells.tolist()}). Free-water DTI requires at least two "
        "non-zero shells; acquire multi-shell DWI data to estimate free-water fraction.",
        RuntimeWarning,
    )

###############################################################################
# The data can then be fitted using the ``fit`` function of the defined model
# object:

fwdtifit = fwdtimodel.fit(data, mask=mask) if can_fit_fwdti else None

###############################################################################
# This 2-steps procedure will create a FreeWaterTensorFit object which contains
# all the diffusion tensor statistics free for free water contamination. Below
# we extract the fractional anisotropy (FA) and the mean diffusivity (MD) of
# the free water diffusion tensor.

FA = fwdtifit.fa if fwdtifit is not None else None
MD = fwdtifit.md if fwdtifit is not None else None

###############################################################################
# For comparison we also compute the same standard measures processed by the
# standard DTI model

dtimodel = dti.TensorModel(gtab)

dtifit = dtimodel.fit(data, mask=mask)

dti_FA = dtifit.fa
dti_MD = dtifit.md
dti_AD = dtifit.ad
dti_RD = dtifit.rd
dti_tensor = dti.lower_triangular(dtifit.quadratic_form)
# Direction-encoded colour (DEC): the principal eigenvector is encoded as
# R/LR, G/AP, B/IS and modulated by fractional anisotropy.
dti_rgb = np.clip(dti.color_fa(dti_FA, dtifit.evecs) * 255, 0, 255).astype(np.uint8)


# Save the full 3-D standard-DTI maps and the six unique tensor elements.
# All outputs retain the affine and voxel grid of the source DWI image.
def save_dti_volume(filename, volume, dtype=np.float32):
    header = img.header.copy()
    header.set_data_dtype(dtype)
    nib.save(
        nib.Nifti1Image(np.asarray(volume, dtype=dtype), img.affine, header),
        args.output_dir / filename,
    )


save_dti_volume("dti_tensor_lower_triangular.nii.gz", dti_tensor)
save_dti_volume("dti_fa.nii.gz", dti_FA)
save_dti_volume("dti_md.nii.gz", dti_MD)
save_dti_volume("dti_ad.nii.gz", dti_AD)
save_dti_volume("dti_rd.nii.gz", dti_RD)
save_dti_volume("dti_rgb.nii.gz", dti_rgb, dtype=np.uint8)
print(
    "Saved full-volume standard-DTI outputs: dti_tensor_lower_triangular.nii.gz, "
    "dti_fa.nii.gz, dti_md.nii.gz, dti_ad.nii.gz, dti_rd.nii.gz, dti_rgb.nii.gz"
)

###############################################################################
# Below the FA values for both free water elimination DTI model and standard
# DTI model are plotted in panels A and B, while the respective MD values are
# plotted in panels D and E. For a better visualization of the effect of the
# free water correction, the differences between these two metrics are shown
# in panels C and E. In addition to the standard diffusion statistics, the
# estimated volume fraction of the free water contamination is shown on
# panel G.

fig1, ax = plt.subplots(2, 4, figsize=(12, 6), subplot_kw={"xticks": [], "yticks": []})

fig1.subplots_adjust(hspace=0.3, wspace=0.05)
if FA is not None:
    ax.flat[0].imshow(
        FA[:, :, args.slice_index].T, origin="lower", cmap="gray", vmin=0, vmax=1
    )
    ax.flat[0].set_title("A) fwDTI FA")
else:
    ax.flat[0].text(
        0.5, 0.5, "fwDTI unavailable\n(single-shell data)", ha="center", va="center"
    )
    ax.flat[0].set_title("A) fwDTI FA")
ax.flat[1].imshow(
    dti_FA[:, :, args.slice_index].T, origin="lower", cmap="gray", vmin=0, vmax=1
)
ax.flat[1].set_title("B) standard DTI FA")

if FA is not None:
    FAdiff = abs(FA[:, :, args.slice_index] - dti_FA[:, :, args.slice_index])
    ax.flat[2].imshow(FAdiff.T, cmap="gray", origin="lower", vmin=0, vmax=1)
    ax.flat[2].set_title("C) FA difference")
else:
    ax.flat[2].axis("off")

ax.flat[3].axis("off")

if MD is not None:
    ax.flat[4].imshow(
        MD[:, :, args.slice_index].T, origin="lower", cmap="gray", vmin=0, vmax=2.5e-3
    )
    ax.flat[4].set_title("D) fwDTI MD")
else:
    ax.flat[4].text(
        0.5, 0.5, "fwDTI unavailable\n(single-shell data)", ha="center", va="center"
    )
    ax.flat[4].set_title("D) fwDTI MD")
ax.flat[5].imshow(
    dti_MD[:, :, args.slice_index].T, origin="lower", cmap="gray", vmin=0, vmax=2.5e-3
)
ax.flat[5].set_title("E) standard DTI MD")

if MD is not None:
    MDdiff = abs(MD[:, :, args.slice_index] - dti_MD[:, :, args.slice_index])
    ax.flat[6].imshow(MDdiff.T, origin="lower", cmap="gray", vmin=0, vmax=2.5e-3)
    ax.flat[6].set_title("F) MD difference")
else:
    ax.flat[6].axis("off")

F = fwdtifit.f if fwdtifit is not None else None
if F is not None:
    ax.flat[7].imshow(
        F[:, :, args.slice_index].T, origin="lower", cmap="gray", vmin=0, vmax=1
    )
    ax.flat[7].set_title("G) free water volume")
else:
    ax.flat[7].axis("off")

fig1.savefig(
    args.output_dir / "In_vivo_free_water_DTI_and_standard_DTI_measures.png", dpi=150
)
plt.close(fig1)

###############################################################################
# .. rst-class:: centered small fst-italic fw-semibold
#
# In vivo diffusion measures obtain from the free water DTI and standard
# DTI. The values of Fractional Anisotropy for the free water DTI model and
# standard DTI model and their difference are shown in the upper panels (A-C),
# while respective MD values are shown in the lower panels (D-F). In addition
# the free water volume fraction estimated from the fwDTI model is shown in
# panel G.
#
#
# From the figure, one can observe that the free water elimination model
# produces in general higher values of FA and lower values of MD than the
# standard DTI model. These differences in FA and MD estimation are expected
# due to the suppression of the free water isotropic diffusion components.
# Unexpected high amplitudes of FA are however observed in the periventricular
# gray matter. This is a known artefact of regions associated to voxels with
# high water volume fraction (i.e. voxels containing basically CSF). We are
# able to remove this problematic voxels by excluding all FA values
# associated with measured volume fractions above a reasonable threshold
# of 0.7:

if F is not None:
    FA[F > 0.7] = 0
    dti_FA[F > 0.7] = 0

###############################################################################
# Above we reproduce the plots of the in vivo FA from the two DTI fits and
# where we can see that the inflated FA values were practically removed:

if FA is not None:
    fig1, ax = plt.subplots(
        1, 3, figsize=(9, 3), subplot_kw={"xticks": [], "yticks": []}
    )
    fig1.subplots_adjust(hspace=0.3, wspace=0.05)
    ax.flat[0].imshow(
        FA[:, :, args.slice_index].T, origin="lower", cmap="gray", vmin=0, vmax=1
    )
    ax.flat[0].set_title("A) fwDTI FA")
    ax.flat[1].imshow(
        dti_FA[:, :, args.slice_index].T, origin="lower", cmap="gray", vmin=0, vmax=1
    )
    ax.flat[1].set_title("B) standard DTI FA")
    FAdiff = abs(FA[:, :, args.slice_index] - dti_FA[:, :, args.slice_index])
    ax.flat[2].imshow(FAdiff.T, cmap="gray", origin="lower", vmin=0, vmax=1)
    ax.flat[2].set_title("C) FA difference")
    fig1.savefig(
        args.output_dir / "In_vivo_free_water_DTI_and_standard_DTI_corrected.png",
        dpi=150,
    )
    plt.close(fig1)

###############################################################################
# .. rst-class:: centered small fst-italic fw-semibold
#
# In vivo FA measures obtain from the free water DTI (A) and standard
# DTI (B) and their difference (C). Problematic inflated FA values of the
# images were removed by dismissing voxels above a volume fraction threshold
# of 0.7.
#
#
# References
# ----------
#
# .. footbibliography::
#

###############################################################################
# .. include:: ../../links_names.inc
#
