#!/usr/bin/env bash

set -euo pipefail

SRC_DIR="/run/media/falconnier/Elements/HCP-Young Adult 2025"
DST_DIR="/home/falconnier/Documents/HCP_Young_Adult_2025"

mkdir -p "$DST_DIR"

find "$SRC_DIR" -maxdepth 1 -type f -name "*.zip" | while read -r zipfile; do
    zipname=$(basename "$zipfile")
    zipbase="${zipname%.zip}"
    extract_dir="$DST_DIR/$zipbase"

    # Skip if already processed (directory exists and is not empty)
    if [[ -d "$extract_dir" ]] && [[ -n "$(ls -A "$extract_dir" 2>/dev/null)" ]]; then
        echo "Skipping (already processed): $zipname"
        continue
    fi

    echo "Processing: $zipname"

    # Copy zip file
    cp "$zipfile" "$DST_DIR/"
    zipcopy="$DST_DIR/$zipname"

    # Create extraction directory
    mkdir -p "$extract_dir"

    # Extract zip
    unzip -q "$zipcopy" -d "$extract_dir"

    # Remove any MNINonLinear directories
    find "$extract_dir" -type d -name "MNINonLinear" -exec rm -rf {} +

    # Remove files that do NOT match allowed patterns
    find "$extract_dir" -type f \
        ! -name "T*w_acpc_dc*.nii.gz" \
        ! -name "brainmask_fs.nii.gz" \
        ! -name "Head.nii.gz" \
        -delete

    # Remove the copied zip file
    rm -f "$zipcopy"

    echo "Finished: $zipname"
    echo
done
