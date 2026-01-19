#!/usr/bin/env bash

set -euo pipefail

SRC_DIR="$1"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Usage: $0 <source_directory>"
  exit 1
fi

echo "Source directory: $SRC_DIR"
echo "--------------------------------------"

############################################
# 1. Extract ZIP files in place
############################################
echo "Extracting ZIP files..."

find "$SRC_DIR" -type f -iname "*.zip" | while read -r zipfile; do
  zipdir="$(dirname "$zipfile")"
  tmpdir="$(mktemp -d)"

  echo "  Extracting: $zipfile"
  unzip -qq "$zipfile" -d "$tmpdir"

  # Merge extracted contents into original directory
  shopt -s dotglob
  mv "$tmpdir"/* "$zipdir"/
  shopt -u dotglob

  rm -rf "$tmpdir"
  rm -f "$zipfile"
done

############################################
# 2. Find DICOM directories and convert
############################################
echo "Converting DICOM folders to NIfTI..."

# Find unique directories containing DICOM files
find "$SRC_DIR" -type f \( -iname "*.dcm" -o -iname "IM*" \) \
  | sed 's|/[^/]*$||' \
  | sort -u \
  | while read -r dicomdir; do

    echo "  Processing DICOM dir: $dicomdir"

    # Output goes into same directory
    dcm2niix \
      -b y \
      -ba y \
      -z y \
      -o "$dicomdir" \
      "$dicomdir" > /dev/null

    # Check if conversion produced any NIfTI files
    if ls "$dicomdir"/*.nii.gz >/dev/null 2>&1; then
      echo "    Conversion successful, removing DICOM files"
      find "$dicomdir" -type f \( -iname "*.dcm" -o -iname "IM*" \) -delete
    else
      echo "    WARNING: No NIfTI produced, DICOMs preserved"
    fi
done

echo "--------------------------------------"
echo "Done."
