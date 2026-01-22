#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$1"

if [ ! -d "$SRC_DIR" ]; then
    echo "ERROR: Source folder does not exist: $SRC_DIR" >&2
    exit 1
fi

echo "Extracting ZIP files in-place under: $SRC_DIR"
echo "--------------------------------------"

find "$SRC_DIR" -type f -iname "*.zip" -print0 |
while IFS= read -r -d '' zipfile; do
    zipdir="$(dirname "$zipfile")"

    echo "  Extracting: $zipfile"
    echo "    → into: $zipdir"

    if unzip -o -qq "$zipfile" -d "$zipdir"; then
        # rm -f "$zipfile"
        echo "    ✔ Extraction successful"
    else
        echo "Extraction failed: $zipfile" >&2
    fi
done

echo "ZIP extraction completed."
