#!/usr/bin/env bash

set -euo pipefail

# ----------------------------
# Usage check
# ----------------------------
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <SOURCE_FOLDER> <DESTINATION_FOLDER>"
    exit 1
fi

SRC="$1"
DST="$2"

# Prefixes for flat layout
SUB_PREFIX="sub-"
SES_PREFIX="ses-"

# ----------------------------
# Validation
# ----------------------------
if [ ! -d "$SRC" ]; then
    echo "ERROR: Source folder does not exist: $SRC"
    exit 1
fi

mkdir -p "$DST"

echo "Flattening BLSA DICOM structure"
echo "Source      : $SRC"
echo "Destination : $DST"
echo



# ----------------------------
# Main loop
# ----------------------------
for subj_path in "$SRC"/*; do
    [ -d "$subj_path" ] || continue


    subj_id="$(basename "$subj_path")"
    subj_out="$DST/${SUB_PREFIX}${subj_id}"

    # Sequence level (e.g. MPrageADNIsag)
    for seq_path in "$subj_path"/*; do
        [ -d "$seq_path" ] || continue

        # Session level (e.g. 2012-05-01_08_32_20.0)
        for ses_path in "$seq_path"/*; do
            [ -d "$ses_path" ] || continue

            ses_raw="$(basename "$ses_path")"
            ses_date="$(echo "$ses_raw" | cut -d_ -f1 | tr -d '-')"

            # ses_out="$subj_out/${SES_PREFIX}${ses_date}"

            seq_name="$(basename "$seq_path")"
            ses_out="$subj_out/${SES_PREFIX}${ses_date}/${seq_name}"

            mkdir -p "$ses_out"

            # Instance level (e.g. I11139448)
            for inst_path in "$ses_path"/*; do
                [ -d "$inst_path" ] || continue

                echo "Processing:"
                echo "  Subject : $subj_id"
                echo "  Session : $ses_date"
                echo "  Source  : $inst_path"

                # Copy DICOM files (non-destructive)
                find "$inst_path" -type f -iname "*.dcm" -exec cp -n {} "$ses_out/" \;
            done
        done
    done
done

echo
echo "Flattening completed successfully."
