#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <SRC_DIR> <DST_DIR> <NUM_JOBS> <TURBO_PREP_PBS>"
    echo "The following are hard coded in the script and may need to be updated:"
    echo "PYTHON path (bin), PIPELINE path (.py script), MNI TEMPLATE path (brain nii.gz template)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRC_DIR="$1"
DST_DIR="$2"
NUM_JOBS="$3"
TURBO_PREP_PBS="$4"

# configurable paths 
PYTHON="$HOME/Documents/mri-preprocessing/.venv/bin/python"
PIPELINE="$HOME/Documents/mri-preprocessing/turboprep-multiple-v2.py"
TEMPLATE="$HOME/Documents/mri-preprocessing/MNI_templates/MNI152_T1_1mm_brain.nii.gz"

INPUTS_TXT="$SCRIPT_DIR/inputs.txt"
OUTPUTS_TXT="$SCRIPT_DIR/outputs.txt"
INPUTS_CHUNK_PREFIX="$SCRIPT_DIR/inputs_chunk_"
OUTPUTS_CHUNK_PREFIX="$SCRIPT_DIR/outputs_chunk_"

echo "Cleaning up existing temporary txt files"
rm -f "$INPUTS_TXT" "$OUTPUTS_TXT" \
      "${INPUTS_CHUNK_PREFIX}"* \
      "${OUTPUTS_CHUNK_PREFIX}"*

find "$SRC_DIR" -type f -iname "*t1w*.nii.gz" > "$INPUTS_TXT"
sed "s|$SRC_DIR|$DST_DIR|" "$INPUTS_TXT" > "$OUTPUTS_TXT"

N=$(wc -l < "$INPUTS_TXT")
K=$NUM_JOBS
L=$(( (N + K - 1) / K ))

echo "Total files: $N, Jobs: $K, Lines per job: $L"

split -l "$L" "$INPUTS_TXT"  "$INPUTS_CHUNK_PREFIX"
split -l "$L" "$OUTPUTS_TXT" "$OUTPUTS_CHUNK_PREFIX"

for f in "${INPUTS_CHUNK_PREFIX}"*; do
    suf=${f#"$INPUTS_CHUNK_PREFIX"}
    echo "Submitting job for chunk $suf"

    qsub \
      -v SUF="$suf",SCRIPT_DIR="$SCRIPT_DIR",PYTHON="$PYTHON",PIPELINE="$PIPELINE",TEMPLATE="$TEMPLATE" \
      "$TURBO_PREP_PBS"
done

echo "Cleaning up temporary txt files"
rm -f "$INPUTS_TXT" "$OUTPUTS_TXT" \
      "${INPUTS_CHUNK_PREFIX}"* \
      "${OUTPUTS_CHUNK_PREFIX}"*
