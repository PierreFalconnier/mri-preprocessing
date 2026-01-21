## commands used for SRPBS dataset
# Compress all .nii files (replace them with .nii.gz)
find . -type f -name "*.nii" -exec gzip {} \;

# # Compress all .nii files but keep the originals
# find . -type f -name "*.nii" -exec gzip -k {} \;

# # raname all "t1" folders to "anat"
# find . -type d -name "t1" -depth -exec bash -c 'mv "$0" "$(dirname "$0")/anat"' {} \;
