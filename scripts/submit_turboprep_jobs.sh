#!/usr/bin/env bash
# Split a dataset's T1w files into NUM_JOBS chunks and submit one PBS
# turboprep job per chunk. Generalized from the legacy
# preprocessing/run_turboprep_jobs.sh to work for any dataset (paths come
# from configs/datasets/<dataset>.yaml).
set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <DATASET> <SRC_DIR> <DST_DIR> <NUM_JOBS>"
    exit 1
fi

DATASET="$1"
SRC_DIR="$2"
DST_DIR="$3"
NUM_JOBS="$4"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_DIR="$REPO_ROOT/scripts/tmp"
LOGS_DIR="$REPO_ROOT/logs"
mkdir -p "$TEMP_DIR" "$LOGS_DIR"

INPUTS_TXT="$TEMP_DIR/inputs.txt"
OUTPUTS_TXT="$TEMP_DIR/outputs.txt"
INPUTS_CHUNK_PREFIX="$TEMP_DIR/inputs_chunk_"
OUTPUTS_CHUNK_PREFIX="$TEMP_DIR/outputs_chunk_"

rm -f "$INPUTS_TXT" "$OUTPUTS_TXT" "${INPUTS_CHUNK_PREFIX}"* "${OUTPUTS_CHUNK_PREFIX}"*

echo "Listing T1w files under $SRC_DIR..."
find "$SRC_DIR" -type f -iname "*t1w*.nii.gz" > "$INPUTS_TXT"
sed "s|$SRC_DIR|$DST_DIR|; s|\.nii\.gz\$||" "$INPUTS_TXT" > "$OUTPUTS_TXT"

N=$(wc -l < "$INPUTS_TXT")
K="$NUM_JOBS"
L=$(( (N + K - 1) / K ))
echo "Total files: $N, jobs: $K, files per job: $L"

split -a 5 -d -l "$L" "$INPUTS_TXT"  "$INPUTS_CHUNK_PREFIX"
split -a 5 -d -l "$L" "$OUTPUTS_TXT" "$OUTPUTS_CHUNK_PREFIX"

for input_chunk in "${INPUTS_CHUNK_PREFIX}"*; do
    suffix="${input_chunk#$INPUTS_CHUNK_PREFIX}"
    output_chunk="${OUTPUTS_CHUNK_PREFIX}${suffix}"

    JOB_NAME="turboprep_${DATASET}_${suffix}"
    qsub -N "$JOB_NAME" \
         -o "${LOGS_DIR}/${JOB_NAME}.out" \
         -e "${LOGS_DIR}/${JOB_NAME}.err" \
         -v "DATASET=$DATASET,IN_FILE=$input_chunk,OUT_FILE=$output_chunk" \
         "$REPO_ROOT/scripts/pbs/turboprep.pbs"
done
