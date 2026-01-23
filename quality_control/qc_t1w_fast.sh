#!/usr/bin/env bash
set -e

T1W=$1
OUTDIR=$2
SUB=$(basename "$T1W" | sed 's/_T1w.nii.gz//')

mkdir -p "$OUTDIR"

# 1. Bias correction (fast, robust)
N4BiasFieldCorrection -d 3 -i "$T1W" -o "$OUTDIR/${SUB}_N4.nii.gz"

# 2. Brain extraction (FAST mode)
bet "$OUTDIR/${SUB}_N4.nii.gz" \
    "$OUTDIR/${SUB}_brain.nii.gz" \
    -f 0.3 -g 0 -R

# 3. Brain volume
BRAIN_VOL=$(fslstats "$OUTDIR/${SUB}_brain.nii.gz" -V | awk '{print $2}')

# 4. Foreground / background SNR proxy
FG_MEAN=$(fslstats "$OUTDIR/${SUB}_brain.nii.gz" -M)
BG_STD=$(fslstats "$OUTDIR/${SUB}_N4.nii.gz" -k "$OUTDIR/${SUB}_brain.nii.gz" -S)

SNR=$(python3 - <<EOF
import math
print(round($FG_MEAN / max($BG_STD, 1e-6), 2))
EOF
)

# 5. QC snapshot
slicer "$OUTDIR/${SUB}_N4.nii.gz" \
       "$OUTDIR/${SUB}_brain.nii.gz" \
       -a "$OUTDIR/${SUB}_qc.png"

# 6. Save metrics
cat <<EOF > "$OUTDIR/${SUB}_qc.json"
{
  "brain_volume_mm3": $BRAIN_VOL,
  "snr_proxy": $SNR
}
EOF
