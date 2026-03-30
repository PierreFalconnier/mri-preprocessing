#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$1"
DST_DIR="$2"

mkdir -p "$DST_DIR"

for d in "$SRC_DIR"/*_StructuralRecommended; do
    base=$(basename "$d")

    # ---- extract subject + session from outer folder ----
    if [[ "$base" =~ ^([^_]+)_V([^_]+)_ ]]; then
        subj="${BASH_REMATCH[1]}"
        ses="V${BASH_REMATCH[2]}"
    else
        subj="${base%%_*}"
        ses="1"
    fi

    # ---- find inner directory robustly ----
    inner_dir=$(find "$d" -mindepth 1 -maxdepth 1 -type d | head -n 1)

    if [[ -z "$inner_dir" ]]; then
        echo "WARNING: no inner directory in $d" >&2
        continue
    fi

    src="$inner_dir/T1w/T1w_acpc_dc.nii.gz"

    dst="$DST_DIR/sub-$subj/ses-$ses/anat"
    out="$dst/sub-${subj}_ses-${ses}_T1w.nii.gz"

    if [[ -f "$src" ]]; then
        mkdir -p "$dst"
        # ln -f "$src" "$out" 2>/dev/null || true
        # rsync -av --ignore-existing "$src" "$out"
        echo "Moving $src to $out"
        mv "$src" "$out"
    else
        echo "WARNING: missing T1w for $base" >&2
    fi
done
