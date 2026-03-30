find /path/to/base -type d -name "*.nii.gz" | while read dir; do
    newdir="${dir%.nii.gz}"   # remove the .nii.gz suffix
    mv "$dir" "$newdir"
done
