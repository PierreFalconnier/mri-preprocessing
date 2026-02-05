#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "Usage: $0 <SRC_DIR> <DST_DIR> <NUM_JOBS>"
    exit 1
fi

# Directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRC_DIR="$1"
DST_DIR="$2"
NUM_JOBS="$3"

INPUTS_TXT="$SCRIPT_DIR/inputs.txt"
OUTPUTS_TXT="$SCRIPT_DIR/outputs.txt"
INPUTS_CHUNK_PREFIX="$SCRIPT_DIR/inputs_chunk_"
OUTPUTS_CHUNK_PREFIX="$SCRIPT_DIR/outputs_chunk_"

# find the files and create the input and output lists
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
    # qsub -v SUF=$suf turboprep.pbs
    echo "Processing chunk $suf"
done

# remove the temporary files
echo "Cleaning up temporary txt files"
rm -f "$INPUTS_TXT" "$OUTPUTS_TXT" \
      "${INPUTS_CHUNK_PREFIX}"* \
      "${OUTPUTS_CHUNK_PREFIX}"*
