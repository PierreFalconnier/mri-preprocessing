#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <SRC_DIR> <CURATION_STATUS_TSV>"
    exit 1
fi

SRC_DIR="$1"
CURATION_TSV="$2"
DST="$3"

# DST=$(dirname "$SRC_DIR")/test_again_post_reorg
mkdir -p "$DST"

SUB_PREFIX="sub-"
SES_PREFIX="ses-"

echo
echo "Flattening DICOM structure (using TSV sessions)"
echo "Source      : $SRC_DIR"
echo "TSV         : $CURATION_TSV"
echo "Destination : $DST"
echo

# ---- build mapping: subject + date → session ----
declare -A SESSION_MAP

while IFS=$'\t' read -r participant session visit _rest; do
    [[ "$participant" == "participant" ]] && continue

    # visit column often contains BL, V04, etc.
    # we assume session column already correct (BL, SC, V04...)

    key="${participant}_${session}"
    SESSION_MAP["$key"]="$session"
done < "$CURATION_TSV"

# ---- main loop ----
for subj_path in "$SRC_DIR"/*; do

    [ -d "$subj_path" ] || continue

    subj_id="$(basename "$subj_path")"
    subj_out="$DST/${SUB_PREFIX}${subj_id}"

    for seq_path in "$subj_path"/*; do
        [ -d "$seq_path" ] || continue

        for ses_path in "$seq_path"/*; do
            [ -d "$ses_path" ] || continue

            ses_raw="$(basename "$ses_path")"
            ses_date="$(echo "$ses_raw" | cut -d_ -f1 | tr -d '-')"

            # ⚠️ HERE: we cannot rely on date directly → try all sessions for subject
            ses_label=""

            for key in "${!SESSION_MAP[@]}"; do
                if [[ "$key" == "${subj_id}_"* ]]; then
                    ses_label="${SESSION_MAP[$key]}"
                    break
                fi
            done

            if [ -z "$ses_label" ]; then
                echo "  [WARNING] No session found for subject $subj_id"
                continue
            fi

            ses_out="$subj_out/${SES_PREFIX}${ses_label}"
            mkdir -p "$ses_out"

            for inst_path in "$ses_path"/*; do
                [ -d "$inst_path" ] || continue

                echo "Processing:"
                echo "  Subject : $subj_id"
                echo "  Session : $ses_label"
                echo "  Source  : $inst_path"

                find "$inst_path" -type f -exec ln -sr -t "$ses_out" {} +
            done
        done
    done
done

echo
echo "Flattening completed successfully."