import argparse

import matplotlib.pyplot as plt
import numpy as np


def show_npy(path):
    img = np.load(path)

    print(f"Shape: {img.shape}, dtype: {img.dtype}")

    plt.imshow(img, cmap="gray")
    plt.title(path)
    plt.axis("off")
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Display a .npy image")
    parser.add_argument("path", type=str, help="Path to .npy file")

    args = parser.parse_args()

    show_npy(args.path)
