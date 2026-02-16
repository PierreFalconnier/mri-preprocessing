#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <SRC_DIR> <DST_DIR> <NUM_JOBS> <TURBO_PREP_PBS>"
    exit 1
fi

TEMP_DIR=$HOME/Documents/mri-preprocessing/preprocessing/tmp
mkdir -p "$TEMP_DIR"

LOGS_DIR=$HOME/Documents/mri-preprocessing/logs
mkdir -p "$LOGS_DIR"

SRC_DIR="$1"
DST_DIR="$2"
TURBO_PREP_PBS="$3"
NUM_JOBS="$4"

INPUTS_TXT="$TEMP_DIR/inputs.txt"
OUTPUTS_TXT="$TEMP_DIR/outputs.txt"
INPUTS_CHUNK_PREFIX="$TEMP_DIR/inputs_chunk_"
OUTPUTS_CHUNK_PREFIX="$TEMP_DIR/outputs_chunk_"

echo "Cleaning up existing temporary txt files"
rm -f "$INPUTS_TXT" "$OUTPUTS_TXT" \
      "${INPUTS_CHUNK_PREFIX}"* \
      "${OUTPUTS_CHUNK_PREFIX}"*

echo "Listing files to process..."
find "$SRC_DIR" -type f -iname "*t1w*.nii.gz" > "$INPUTS_TXT"
sed "s|$SRC_DIR|$DST_DIR|" "$INPUTS_TXT" > "$OUTPUTS_TXT"

N=$(wc -l < "$INPUTS_TXT")
K=$NUM_JOBS
L=$(( (N + K - 1) / K ))
echo "Total files: $N, Jobs: $K, Lines per job: $L"

split -a 2 -d -l "$L" "$INPUTS_TXT"  "$INPUTS_CHUNK_PREFIX"
split -a 2 -d -l "$L" "$OUTPUTS_TXT" "$OUTPUTS_CHUNK_PREFIX"

# Loop through the generated input chunks
for input_chunk in "${INPUTS_CHUNK_PREFIX}"*; do
    # Identify the suffix to find the matching output chunk
    suffix="${input_chunk#$INPUTS_CHUNK_PREFIX}"
    output_chunk="${OUTPUTS_CHUNK_PREFIX}${suffix}"
    echo "Submitting job for:"
    echo "input: $input_chunk"
    echo "output: $output_chunk"

    JOB_NAME="turbo_prep_${suffix}"
    OUT_LOG="${LOGS_DIR}/${JOB_NAME}.out"
    ERR_LOG="${LOGS_DIR}/${JOB_NAME}.err"

    # Pass the chunk paths as environment variables to the PBS script
    qsub -N "$JOB_NAME" \
         -o "$OUT_LOG" \
         -e "$ERR_LOG" \
         -v "IN_FILE=$input_chunk,OUT_FILE=$output_chunk" \
         "$TURBO_PREP_PBS"

    # qsub -v "IN_FILE=$input_chunk,OUT_FILE=$output_chunk" "$TURBO_PREP_PBS"

done