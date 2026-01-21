#!/bin/bash

PROJECT_PATH="$1"

# Find symlinks matching *T1w*.nii.gz in this project folder
find "$PROJECT_PATH" -type l | while IFS= read -r LINK; do
# find "$PROJECT_PATH" -type l -name "**.json" | while IFS= read -r LINK; do
# find "$PROJECT_PATH" -type l -name "**.nii.gz" | while IFS= read -r LINK; do
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
        echo "Removing the link anyway."
        rm "$LINK"
    fi
done
