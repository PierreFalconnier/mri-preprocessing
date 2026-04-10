import os
from pathlib import Path

import pandas as pd
from tqdm import tqdm

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", required=True, help="path of the root of the dataset"
    )
    parser.add_argument(
        "--output", required=True, help="path of the root of the dataset"
    )
    parser.add_argument("--csv", required=True, help="path of the root of the dataset")

    args = parser.parse_args()

    INPUT_DIR = Path(args.source)
    OUTPUT_DIR = Path(args.output)
    CSV_PATH = Path(args.csv)

    # -----------------------------
    # Load CSV
    # -----------------------------
    df = pd.read_csv(CSV_PATH)

    df["image_id"] = df["image_id"].astype(str).str.strip()

    # convert date column
    df["image_date"] = pd.to_datetime(
        df["image_date"], errors="coerce", format="mixed", dayfirst=False
    )

    df["ses"] = df["image_date"].dt.strftime("%Y%m%d")

    # index for fast lookup
    date_map = df.set_index("image_id")[["subject_id", "ses"]].to_dict("index")

    # -----------------------------
    # Helper: create symlink safely
    # -----------------------------
    def make_symlink(src, dst):
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            os.symlink(src, dst)

    # -----------------------------
    # Iterate dataset
    # -----------------------------
    for folder in tqdm(INPUT_DIR.iterdir(), desc="Processing folders"):
        if not folder.is_dir():
            continue

        # parse folder name
        parts = folder.name.split("_")
        subject_id = "_".join(parts[:3])  # 002_S_0938
        image_id = parts[3]

        if image_id not in date_map:
            print(f"Skipping {folder.name}, no CSV match")
            continue

        ses = date_map[image_id]["ses"]

        out_dir = OUTPUT_DIR / f"sub-{subject_id}" / f"ses-{ses}" / "anat"

        # -----------------------------
        # create BIDS-like filenames
        # -----------------------------
        for file in folder.iterdir():
            if file.is_file():
                out_name = f"sub-{subject_id}_ses-{ses}_T1w_{file.name}"
                out_path = out_dir / out_name

                make_symlink(file.resolve(), out_path)

    print("Done.")
    print("Done.")
