#!/usr/bin/env bash

set -euo pipefail

SRC_DIR="/run/media/falconnier/Elements/HCP-Young Adult 2025"
DST_DIR="/run/media/falconnier/Elements/HCP_YOUNG_filtered"
MAX_JOBS=1
# MAX_JOBS=$(nproc)
DELETE_ZIP_AFTER_EXTRACTION=true

mkdir -p "$DST_DIR"

process_zip() {
    zipfile="$1"
    zipname=$(basename "$zipfile")
    zipbase="${zipname%.zip}"
    extract_dir="$DST_DIR/$zipbase"

    has_t1w() {
        find "$extract_dir" -type f -name "T1w_acpc_dc.nii.gz" | grep -q .
    }

    # Skip if already processed (directory exists and is not empty)
    if [[ -d "$extract_dir" ]] && [[ -n "$(ls -A "$extract_dir" 2>/dev/null)" ]]; then
        echo "Skipping (already processed): $zipname"

        if [[ "$DELETE_ZIP_AFTER_EXTRACTION" = true ]]; then
            if has_t1w; then
                rm -f "$zipfile"
                echo "Deleted ZIP (already processed): $zipname"
            else
                echo "WARNING: Missing T1w_acpc_dc.nii.gz → ZIP NOT deleted: $zipname"
            fi
        fi
        return
    fi

    echo "Processing: $zipname"

    mkdir -p "$extract_dir"

    if unzip -q "$zipfile" -d "$extract_dir"; then
        echo "Extraction completed: $zipname"

        # Remove any MNINonLinear directories
        find "$extract_dir" -type d -name "MNINonLinear" -exec rm -rf {} +

        # Keep only allowed files
        find "$extract_dir" -type f \
            ! -name "T*w_acpc_dc*.nii.gz" \
            ! -name "brainmask_fs.nii.gz" \
            ! -name "Head.nii.gz" \
            -delete

        if [[ "$DELETE_ZIP_AFTER_EXTRACTION" = true ]]; then
            if has_t1w; then
                rm -f "$zipfile"
                echo "Deleted ZIP: $zipname"
            else
                echo "WARNING: Missing T1w_acpc_dc.nii.gz → ZIP NOT deleted: $zipname"
            fi
        fi
    else
        echo "Extraction failed: $zipname"
    fi

    echo "Finished: $zipname"
    echo
}

export -f process_zip
export DST_DIR
export DELETE_ZIP_AFTER_EXTRACTION

find "$SRC_DIR" -maxdepth 1 -type f -name "*.zip" -print0 | \
    xargs -0 -P "$MAX_JOBS" -I {} bash -c 'process_zip "$@"' _ {}
