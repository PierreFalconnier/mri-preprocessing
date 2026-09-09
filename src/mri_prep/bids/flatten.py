"""Flatten a raw ida.loni download tree into sub-*/ses-YYYYMMDD/<sequence>/
so it's easy to walk when converting to BIDS.

Python port of the legacy `bash_scripts/ida_flatten.sh`. Source layout is
assumed to be: <subject>/<sequence description>/<session dir starting with
a date>/<instance dir>/<dicom files...>
"""

from __future__ import annotations

import os
from pathlib import Path

from tqdm import tqdm


def flatten_ida_download(src_dir: Path, dst_dir: Path) -> None:
    src_dir, dst_dir = Path(src_dir), Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    subject_dirs = [p for p in src_dir.iterdir() if p.is_dir()]
    for subject_dir in tqdm(subject_dirs, desc="subjects"):
        subject_id = subject_dir.name
        subject_out = dst_dir / f"sub-{subject_id}"

        for seq_dir in subject_dir.iterdir():
            if not seq_dir.is_dir():
                continue
            seq_name = seq_dir.name

            for ses_dir in seq_dir.iterdir():
                if not ses_dir.is_dir():
                    continue
                # session dir name looks like "2007-06-22_11_25_43.0"
                ses_date = ses_dir.name.split("_")[0].replace("-", "")
                ses_out = subject_out / f"ses-{ses_date}" / seq_name
                ses_out.mkdir(parents=True, exist_ok=True)

                for instance_dir in ses_dir.iterdir():
                    if not instance_dir.is_dir():
                        continue
                    for f in instance_dir.iterdir():
                        if not f.is_file():
                            continue
                        dst_file = ses_out / f.name
                        if not dst_file.exists():
                            os.link(f, dst_file)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    args = parser.parse_args()
    flatten_ida_download(args.source, args.dest)
