import argparse

import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np


def plot_middle_slices(nii_path):
    # Load NIfTI image
    img = nib.load(nii_path)
    data = img.get_fdata()

    print(f"Image shape: {data.shape}")

    print(nib.aff2axcodes(img.affine))

    # Compute middle indices
    x_mid = 5 * data.shape[0] // 10
    y_mid = 5 * data.shape[1] // 10
    z_mid = 5 * data.shape[2] // 10

    # Extract slices
    sagittal = data[x_mid, :, :]
    coronal = data[:, y_mid, :]
    axial = data[:, :, z_mid]

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    axes[0].imshow(np.rot90(sagittal), cmap="gray")
    axes[0].set_title("Sagittal (X mid)")
    axes[0].axis("off")

    axes[1].imshow(np.rot90(coronal), cmap="gray")
    axes[1].set_title("Coronal (Y mid)")
    axes[1].axis("off")

    axes[2].imshow(np.rot90(axial), cmap="gray")
    axes[2].set_title("Axial (Z mid)")
    axes[2].axis("off")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot middle slices of a NIfTI image")
    parser.add_argument("nii_path", type=str, help="Path to .nii or .nii.gz file")

    args = parser.parse_args()

    plot_middle_slices(args.nii_path)
