import argparse
import os

import imageio
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np


def normalize_for_display(data):
    """Robust normalization for visualization"""
    vmin, vmax = np.percentile(data, [1, 99])
    data = np.clip(data, vmin, vmax)
    data = (data - vmin) / (vmax - vmin)
    return data


def create_gif(data, axis, output_path):
    frames = []

    n_slices = data.shape[axis]
    print(f"Creating GIF for axis {axis} with {n_slices} slices")

    for i in range(n_slices):
        if axis == 0:
            slice_ = data[i, :, :]
        elif axis == 1:
            slice_ = data[:, i, :]
        else:
            slice_ = data[:, :, i]

        # Rotate for nicer orientation
        slice_ = np.rot90(slice_)

        # Render slice with matplotlib
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.imshow(slice_, cmap="gray")
        ax.axis("off")

        # Convert plot to image array
        fig.canvas.draw()
        # frame = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
        frame = np.asarray(fig.canvas.buffer_rgba())
        frame = frame[:, :, :3]  # drop alpha channel
        frame = frame.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        frames.append(frame)

        plt.close(fig)

    # Save GIF
    imageio.mimsave(output_path, frames, duration=0.05)
    print(f"Saved: {output_path}")


def main(nii_path):
    img = nib.load(nii_path)
    data = img.get_fdata()

    print(f"Loaded image: {nii_path}")
    print(f"Shape: {data.shape}")

    data = normalize_for_display(data)

    base = os.path.splitext(os.path.splitext(nii_path)[0])[0]

    create_gif(data, axis=0, output_path=base + "_sagittal.gif")
    create_gif(data, axis=1, output_path=base + "_coronal.gif")
    create_gif(data, axis=2, output_path=base + "_axial.gif")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate slice GIFs from NIfTI image")
    parser.add_argument("nii_path", type=str, help="Path to .nii or .nii.gz file")

    args = parser.parse_args()

    main(args.nii_path)
