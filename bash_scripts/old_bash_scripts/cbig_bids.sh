#!/usr/bin/env bash
set -euo pipefail

SRC="$1"
DEST="$2"

if [ $# -ne 2 ]; then
    echo "Usage: $0 <source_dir> <destination_dir>"
    exit 1
fi

mkdir -p "$DEST"

find "$SRC" -path "*/sub-*" -type d -print0 |
while IFS= read -r -d '' d; do
    rsync -a "$d/" "$DEST/$(basename "$d")/"
done
