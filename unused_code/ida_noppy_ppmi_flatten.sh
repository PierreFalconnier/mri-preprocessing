#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <SRC_DIR> <CURATION_STATUS_TSV>"
    echo "Example: $0 ~/downloads/ppmi sourcedata/imaging/curation_status.tsv"
    exit 1
fi

SRC_DIR="$1"              # path to your current extracted dataset
CURATION_TSV="$2"         # path to curation_status.tsv

DST=$(dirname "$SRC_DIR")/pre_reorg
mkdir -p "$DST"

echo
echo "Reorganizing DICOM structure for Nipoppy (all sessions)"
echo "Source           : $SRC_DIR"
echo "Curation TSV     : $CURATION_TSV"
echo "Destination root : $DST"
echo

# Read participant-session pairs from curation_status.tsv
while IFS=$'\t' read -r participant session _rest; do
    # skip header
    [[ "$participant" == "participant" ]] && continue

    ses_folder="ses-$session"  # prepend ses-

    echo "Processing participant $participant, session $ses_folder"

    subj_src="$SRC_DIR/$participant"
    if [ ! -d "$subj_src" ]; then
        echo "  [WARNING] Participant folder not found: $subj_src"
        continue
    fi

    ses_out="$DST/$ses_folder/$participant"
    mkdir -p "$ses_out"

    # Iterate over all sequences/timestamps/series
    for seq_path in "$subj_src"/*; do
        [ -d "$seq_path" ] || continue

        for date_path in "$seq_path"/*; do
            [ -d "$date_path" ] || continue

            for series_path in "$date_path"/*; do
                [ -d "$series_path" ] || continue
                series_id="$(basename "$series_path")"

                series_out="$ses_out/$series_id"
                mkdir -p "$series_out"

                echo "  Linking series $series_id from $series_path"

                # create relative symlinks for all DICOM files in this series
                find "$series_path" -type f -exec ln -sr -t "$series_out" {} +
            done
        done
    done
done < "$CURATION_TSV"

echo
echo "DICOM reorganization completed successfully."