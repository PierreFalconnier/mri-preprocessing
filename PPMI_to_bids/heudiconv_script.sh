#!/bin/bash

HEURISTIC="/home/falconnier/Documents/mri-preprocessing/PPMI_to_bids/heuristic.py"
RAW_DATA_DIR="/run/media/falconnier/bb9ecfb7-b58f-41e9-a37fda12951eb4e/extracted/no_seq"
OUTPUT_DIR="/run/media/falconnier/bb9ecfb7-b58f-41e9-a37fda12951eb4e/NIFTI"

mkdir -p "${OUTPUT_DIR}"



# 2. Loop through subjects
for SUB_PATH in "${RAW_DATA_DIR}"/sub-*; do

    echo "Processing Subject Path: ${SUB_PATH}"
    # Check if the path exists to avoid the "*" error you saw
    [ -e "$SUB_PATH" ] || continue
    
    SUB_ID=$(basename "${SUB_PATH}" | sed 's/sub-//')
    
    # # 3. Loop through sessions
    # for SES_PATH in "${SUB_PATH}"/ses-*; do
    #     [ -e "$SES_PATH" ] || continue
        
    #     SES_ID=$(basename "${SES_PATH}" | sed 's/ses-//')
        
    #     echo "------------------------------------------------"
    #     echo "Processing Subject: ${SUB_ID}, Session: ${SES_ID}"
    #     echo "------------------------------------------------"
        
    #     # 4. Run Heudiconv
    #     # Note: We use quotes around variables to prevent shell expansion errors
    #     heudiconv \
    #         --files "${RAW_DATA_DIR}/sub-${SUB_ID}/ses-${SES_ID}"/*/*.dcm \
    #         -o "${OUTPUT_DIR}" \
    #         -f "${HEURISTIC}" \
    #         -s "${SUB_ID}" \
    #         -ss "${SES_ID}" \
    #         -c dcm2niix \
    #         -b --minmeta --overwrite
    # done
done