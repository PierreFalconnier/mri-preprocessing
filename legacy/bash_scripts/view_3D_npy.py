import argparse

import matplotlib.pyplot as plt
import numpy as np


def show_npy_3d(path):
    # if nii, convertor to npy first using nibabel, then load the npy
    if path.endswith(".nii") or path.endswith(".nii.gz"):
        import nibabel as nib

        nii = nib.load(path)
        vol = nii.get_fdata()
    else:
        vol = np.load(path)
    if vol.ndim == 4:
        vol = vol[0]
    if vol.ndim == 5:
        vol = vol[0, 0]
    if vol.ndim != 3:
        raise ValueError(f"Expected a 3D array, got shape {vol.shape}")

    print(f"Shape: {vol.shape}, dtype: {vol.dtype}")

    # Mid-slice indices
    z_mid = vol.shape[0] // 2
    y_mid = vol.shape[1] // 2
    x_mid = vol.shape[2] // 2

    # Extract slices
    axial = vol[z_mid, :, :]  # along axis 0
    coronal = vol[:, y_mid, :]  # along axis 1
    sagittal = vol[:, :, x_mid]  # along axis 2

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    axes[0].imshow(axial, cmap="gray")
    axes[0].set_title(f"Axis 0 slice @ {z_mid}")
    axes[0].axis("off")

    axes[1].imshow(coronal, cmap="gray")
    axes[1].set_title(f"Axis 1 slice @ {y_mid}")
    axes[1].axis("off")

    axes[2].imshow(sagittal, cmap="gray")
    axes[2].set_title(f"Axis 2 slice @ {x_mid}")
    axes[2].axis("off")

    plt.suptitle(path)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Display middle slices of a 3D .npy volume"
    )
    parser.add_argument("path", type=str, help="Path to .npy file")

    args = parser.parse_args()

    show_npy_3d(args.path)
