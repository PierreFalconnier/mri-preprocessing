#!/bin/bash

BASE_DIR="$HOME/Documents/data/BIDS_datasets_selection_v2_processed_reorganized"
CURATED_BASE="$HOME/Documents/data/BIDS_datasets_selection_v2_curated"
LOG_DIR="$HOME/Documents/mri-preprocessing/logs"
PBS_SCRIPT="$HOME/Documents/mri-preprocessing/quality_control/run_qc_job.pbs"

mkdir -p "$LOG_DIR"

for dataset_path in "$BASE_DIR"/*/; do
    # Remove trailing slash and extract dataset name
    dataset_path="${dataset_path%/}"
    dataset_name=$(basename "$dataset_path")

    echo "Submitting job for $dataset_name"
    # echo "Dataset path: $dataset_path"
    # echo "Curated directory: $CURATED_BASE/$dataset_name"
    # echo "Log output: $LOG_DIR/${dataset_name}.out"
    # echo "Log error: $LOG_DIR/${dataset_name}.err"
    # echo "Job name: qc_${dataset_name}"
    # echo "----------------------------------------"


    qsub \
        -N "qc_${dataset_name}" \
        -o "$LOG_DIR/${dataset_name}.out" \
        -e "$LOG_DIR/${dataset_name}.err" \
        -v SOURCE_DIR="$dataset_path",DATASET_NAME="$dataset_name",CURATED_DIR="$CURATED_BASE/$dataset_name" \
        "$PBS_SCRIPT"
done