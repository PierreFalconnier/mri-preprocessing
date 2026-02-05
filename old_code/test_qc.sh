find /home/falconnier/Downloads/CamCAN -name "*_T1w.nii.gz" | while read T1W; do
  SUB=$(basename "$T1W" | sed 's/_T1w.nii.gz//')
  /home/falconnier/Documents/mri-preprocessing/quality_control/qc_t1w_fast.sh "$T1W" "qc_out/$SUB"
done
