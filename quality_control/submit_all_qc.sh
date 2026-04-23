#!/bin/bash

BASE_DIR="$HOME/Documents/data/BIDS_datasets_selection_v2_processed_reorganized"
CURATED_BASE="$HOME/Documents/data/BIDS_datasets_selection_v2_curated"

for dataset_path in "$BASE_DIR"/*/; do
    # Remove trailing slash and extract dataset name
    dataset_path="${dataset_path%/}"
    dataset_name=$(basename "$dataset_path")

    echo "Submitting job for $dataset_name"

    # qsub -v \
    #     SOURCE_DIR="$dataset_path",\
    #     DATASET_NAME="$dataset_name",\
    #     CURATED_DIR="$CURATED_BASE/$dataset_name" \
    #     run_qc_job.sh
done