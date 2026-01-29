#!/bin/bash

# -------------------------------
# Config
# -------------------------------
URL_FILE="urls.txt"
TMP_DIR="hcp_download_temp"
URL_PATTERN=".*V4.*unproc.*\.tar\.gz"
PARALLEL_JOBS=1   # Adjust based on your machine/cluster

mkdir -p "$TMP_DIR"

# -------------------------------
# Function to process a single URL
# -------------------------------
process_url() {
    url="$1"

    # Extract patient ID (number before .tar.gz in path)
    patient_id=$(echo "$url" | grep -oP '(?<=/)[0-9]+(?=\.tar\.gz)')
    if [ -z "$patient_id" ]; then
        echo "ERROR: Could not extract patient ID from $url"
        return 1
    fi

    echo "Processing URL $url for patient $patient_id"

    # Patient directory
    patient_dir="$TMP_DIR/$patient_id"
    

    # Skip patient if already processed
    if [ -d "$patient_dir/T1w_MPR1" ] && [ -d "$patient_dir/T2w_SPC1" ]; then
        echo "Patient $patient_id already processed. Skipping."
        return 0
    fi

    # -------------------------------
    # Download using --content-disposition
    # -------------------------------
    mkdir -p "$patient_dir"

    echo "Downloading patient $patient_id..."

    wget -c \
        --tries=0 \
        --timeout=120 \
        --waitretry=30 \
        --retry-connrefused \
        --read-timeout=120 \
        --dns-timeout=30 \
        --continue \
        --no-http-keep-alive \
        --content-disposition \
        -P "$patient_dir" \
        "$url"


    # Get actual filename downloaded
    tmp_file=$(ls "$patient_dir"/*.tar.gz | head -n 1)

    # -------------------------------
    # Verify tarball before extraction
    # -------------------------------
    if ! tar -tzf "$tmp_file" > /dev/null; then
        echo "Tarball verification failed: $tmp_file"
        rm -f "$tmp_file"
        return 1
    fi

    # -------------------------------
    # Extract tarball (structure preserved)
    # -------------------------------
    tar -xzf "$tmp_file" -C "$patient_dir"

    # Remove tarball after extraction
    rm -f "$tmp_file"

    # -------------------------------
    # Keep only desired anatomical directories
    # -------------------------------
    find "$patient_dir" -maxdepth 1 -type d ! \( \
        -name "T1w*" -o \
        -name "T2w*" -o \
        -name "." \
    \) -exec rm -rf {} +

    echo "Finished processing patient $patient_id"
}

# -------------------------------
# Export function for xargs parallel
# -------------------------------
export -f process_url
export TMP_DIR

# -------------------------------
# Run in parallel
# -------------------------------
grep -E "$URL_PATTERN" "$URL_FILE" | \
xargs -n 1 -P $PARALLEL_JOBS bash -c 'process_url "$@"' _

echo "All downloads and processing complete."
