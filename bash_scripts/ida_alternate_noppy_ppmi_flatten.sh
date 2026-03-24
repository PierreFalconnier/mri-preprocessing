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

    # Participant folder in the source dataset
    subj_src="$SRC_DIR/$participant"
    if [ ! -d "$subj_src" ]; then
        echo "  [WARNING] Participant folder not found: $subj_src"
        continue
    fi

    # Destination path: subjects / session
    subj_out="$DST/sub-$participant/$ses_folder"
    mkdir -p "$subj_out"

    # Iterate over sequences (e.g., 2D_GRE-MT, 3D_T1-weighted, DTI_LR, DTI_RL)
    for seq_path in "$subj_src"/*; do
        [ -d "$seq_path" ] || continue
        seq_name="$(basename "$seq_path")"

        # Iterate over timestamps / acquisitions
        for date_path in "$seq_path"/*; do
            [ -d "$date_path" ] || continue

            # Iterate over series folders
            for series_path in "$date_path"/*; do
                [ -d "$series_path" ] || continue
                series_id="$(basename "$series_path")"

                series_out="$subj_out/$series_id"
                mkdir -p "$series_out"

                echo "  Linking sequence $seq_name, series $series_id from $series_path"

                # create relative symlinks for all DICOM files in this series
                find "$series_path" -type f -exec ln -sr -t "$series_out" {} +
            done
        done
    done
done < "$CURATION_TSV"

echo
echo "DICOM reorganization completed successfully."