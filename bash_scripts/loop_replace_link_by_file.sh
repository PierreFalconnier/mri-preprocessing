#!/bin/bash

# List of project subfolders to process
PROJECTS=(
    "AdolescentBrainDevelopment"
    "1000GenomesProject"
    "calgary-campinas"
    "mica-mics"
    "Neurocon"
    "CHBMP"
    "preventad-open-bids/BIDS_dataset"
)

BASE="/home/falconnier/Documents/datasets laptop/conp-dataset/projects"

for PROJECT in "${PROJECTS[@]}"; do
    PROJECT_PATH="$BASE/$PROJECT"
    echo "Processing project: $PROJECT_PATH"

    # Find symlinks matching *T1w*.nii.gz in this project folder
    find "$PROJECT_PATH" -type l -name "*T1w*.nii.gz" | while IFS= read -r LINK; do
        TARGET=$(readlink -f "$LINK")
        if [ -n "$TARGET" ]; then
            echo "Replacing symlink: $LINK"
            echo "With file: $TARGET"
            # Remove the symlink
            rm "$LINK"
            # Copy the target to the original link's location
            cp "$TARGET" "$LINK"
        else
            echo "Warning: could not resolve $LINK"
        fi
    done
done
