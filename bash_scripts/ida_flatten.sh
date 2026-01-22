#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$1" # exctracted full dataset

DST=$(dirname "$SRC_DIR")/flattened
mkdir -p "$DST"

SUB_PREFIX="sub-"
SES_PREFIX="ses-"

echo
echo "Flattening DICOM structure"
echo "Source      : $SRC_DIR"
echo "Destination : $DST"
echo


for subj_path in "$SRC_DIR"/*; do

    [ -d "$subj_path" ] || continue

    subj_id="$(basename "$subj_path")"
    subj_out="$DST/${SUB_PREFIX}${subj_id}"

    for seq_path in "$subj_path"/*; do
        [ -d "$seq_path" ] || continue
        seq_name="$(basename "$seq_path")"

        for ses_path in "$seq_path"/*; do
            [ -d "$ses_path" ] || continue

            ses_raw="$(basename "$ses_path")"
            ses_date="$(echo "$ses_raw" | cut -d_ -f1 | tr -d '-')"

            ses_out="$subj_out/${SES_PREFIX}${ses_date}/${seq_name}"
            mkdir -p "$ses_out"

            for inst_path in "$ses_path"/*; do
                [ -d "$inst_path" ] || continue

                echo "Processing:"
                echo "  Subject : $subj_id"
                echo "  Session : $ses_date"
                echo "  Source  : $inst_path"

                find "$inst_path" -type f -exec cp -n {} "$ses_out/" \;
            done
        done
    done
done

echo
echo "Flattening completed successfully."