import argparse
import os

import nibabel as nib


def get_orientation(img):
    return nib.orientations.aff2axcodes(img.affine)


def to_ras(img):
    return nib.as_closest_canonical(img)


def process_file(path, overwrite=False):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    img = nib.load(path)

    current_orient = get_orientation(img)
    print(f"[INFO] Current orientation: {current_orient}")

    if current_orient == ("R", "A", "S"):
        print("[INFO] Already RAS. No conversion needed.")
        return

    return
    print("[INFO] Converting to RAS...")

    img_ras = to_ras(img)
    new_orient = get_orientation(img_ras)

    print(f"[INFO] New orientation: {new_orient}")

    if overwrite:
        out_path = path
    else:
        out_path = path.replace(".nii.gz", "_RAS.nii.gz")

    nib.save(img_ras, out_path)
    print(f"[INFO] Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Fix NIfTI orientation to RAS")

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to input .nii.gz file",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite original file instead of creating a new one",
    )

    args = parser.parse_args()

    process_file(args.input, args.overwrite)


if __name__ == "__main__":
    main()
