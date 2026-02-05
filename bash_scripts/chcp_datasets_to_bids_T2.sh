#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$1"
DST_DIR="$2"

mkdir -p "$DST_DIR"

for subj_dir in "$SRC_DIR"/*; do
    [[ -d "$subj_dir" ]] || continue  # skip non-directories
    subj=$(basename "$subj_dir")
    ses="1"  # default session

    # path to T1w
    src="$subj_dir/T2w_MPR1/${subj}_3T_T2w_SPC1.nii.gz"
    dst="$DST_DIR/sub-$subj/ses-$ses/anat"
    out="$dst/sub-${subj}_ses-${ses}_T2w.nii.gz"

    if [[ -f "$src" ]]; then
        mkdir -p "$dst"
        echo "Moving $src to $out"
        mv "$src" "$out"
    else
        echo "WARNING: missing T1w for subject $subj" >&2
    fi
done
