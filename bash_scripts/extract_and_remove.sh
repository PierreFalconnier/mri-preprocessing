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
