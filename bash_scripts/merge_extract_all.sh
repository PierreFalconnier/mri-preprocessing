
#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <zip_folder> <output_folder>"
  exit 1
fi

ZIP_DIR="$1"
OUT_DIR="$2"

mkdir -p "$OUT_DIR"

shopt -s nullglob

for zip in "$ZIP_DIR"/*.zip; do
  echo "Extracting: $(basename "$zip")"
  unzip -o "$zip" -d "$OUT_DIR"
#   unzip -n "$zip" -d "$OUT_DIR"
done

echo "Done."
