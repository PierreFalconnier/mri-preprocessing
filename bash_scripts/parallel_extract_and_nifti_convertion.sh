#!/usr/bin/env bash

set -euo pipefail

SRC_DIR="$1"
N_JOBS=$(( $(nproc) / 2 ))
(( N_JOBS < 1 )) && N_JOBS=1

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Usage: $0 <source_directory>"
  exit 1
fi

echo "Source directory: $SRC_DIR"
echo "Parallel jobs: $N_JOBS"
echo "--------------------------------------"

############################################
# 1. Extract ZIP files in place (PARALLEL)
############################################
echo "Extracting ZIP files (parallel)..."

find "$SRC_DIR" -type f -iname "*.zip" \
  | sort \
  | xargs -n 1 -P 1 -I {} bash -c '
    zipfile="{}"
    zipdir="$(dirname "$zipfile")"
    tmpdir="$(mktemp -d)"

    echo "  Extracting $zipfile into $zipdir"
    unzip -qq "$zipfile" -d "$tmpdir"

    # Merge tmpdir into zipdir safely
    rsync -a "$tmpdir"/ "$zipdir"/

    rm -rf "$tmpdir"
    rm -f "$zipfile"
  '

############################################
# 2. Find DICOM directories and convert (PARALLEL)
############################################

# Remove DICOMs even if conversion fails (true / false)
REMOVE_DCM_ON_FAIL=false

echo "Converting DICOM folders to NIfTI (parallel)..."

find "$SRC_DIR" -type f \( -iname "*.dcm" -o -iname "IM*" \) \
  | sed 's|/[^/]*$||' \
  | sort -u \
  | xargs -P "$N_JOBS" -I {} bash -c '
      dicomdir="{}"
      echo "  Processing DICOM dir: $dicomdir"

      dcm2niix \
        -v 2 \
        -b y \
        -ba y \
        -z y \
        -o "$dicomdir" \
        "$dicomdir" > /dev/null

      if ls "$dicomdir"/*.nii.gz >/dev/null 2>&1; then
        echo "    Conversion successful, removing DICOM files"
        find "$dicomdir" -type f \( -iname "*.dcm" -o -iname "IM*" \) -delete
      else
        if [[ "'"$REMOVE_DCM_ON_FAIL"'" == "true" ]]; then
          echo "    WARNING: No NIfTI produced, removing DICOM files anyway"
          find "$dicomdir" -type f \( -iname "*.dcm" -o -iname "IM*" \) -delete
        else
          echo "    WARNING: No NIfTI produced, DICOMs preserved"
        fi
      fi
    '

echo "--------------------------------------"
echo "Done."
