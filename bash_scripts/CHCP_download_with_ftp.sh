#!/bin/bash

REMOTE="ftp.scidb.cn"
REMOTE_DIR="/CHCP_ScienceDB_unproc"
TMP_DIR="hcp_download_temp"

mkdir -p "$TMP_DIR"

# Get remote file list (client-side, reliable)
echo "Fetching file list from $REMOTE_DIR ..."
FILES=$(lftp -u nqUVJz,ENfqau -p 2121 "$REMOTE" -e "cd $REMOTE_DIR; cls -1 *.tar.gz; bye")
echo "Found $(echo "$FILES" | wc -l) tar.gz files."

for filename in $FILES; do
    echo "=============================="
    echo "Processing $filename"

    # Extract patient ID
    patient_id=$(echo "$filename" | grep -oP '[0-9]+(?=\.tar\.gz)')
    if [ -z "$patient_id" ]; then
        echo "Skipping $filename (cannot extract patient ID)"
        continue
    fi

    patient_dir="$TMP_DIR/$patient_id"

    # Skip if already processed
    if [ -d "$patient_dir/T1w_MPR1" ] && [ -d "$patient_dir/T2w_SPC1" ]; then
        echo "Patient $patient_id already processed. Skipping."
        continue
    fi

    mkdir -p "$patient_dir"

    echo "Downloading $filename"
    
    lftp -u nqUVJz,ENfqau -p 2121 "$REMOTE" <<EOF
    set xfer:clobber on 
    set ftp:passive-mode on
    set cmd:fail-exit yes
    cd "$REMOTE_DIR"
    pget -c -n 4 "$filename" -o "$patient_dir/$filename"
    bye
EOF


    tarfile="$patient_dir/$filename"

    # Verify tarball
    echo "Verifying tarball $filename"
    if ! tar -tzf "$tarfile" > /dev/null; then
        echo "Tarball verification failed: $filename"
        # rm -f "$tarfile"
        continue
    fi

    # Extract
    echo "Extracting $filename"
    tar -xzf "$tarfile" -C "$patient_dir"

    # Remove tar immediately
    rm -f "$tarfile"

    # Keep only desired anatomical directories
    find "$patient_dir" -type f ! \( \
        -path "*T1w*.nii.gz" -o \
        -path "*T2w*.nii.gz" \
    \) -exec rm -rf {} +

    echo "Finished patient $patient_id"
done

echo "All patients processed."
