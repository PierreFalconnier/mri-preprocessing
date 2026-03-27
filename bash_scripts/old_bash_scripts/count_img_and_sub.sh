for d in */; do
  echo "Folder: $d"
  
  t1w_count=$(find "$d" -type f -iname "*t1w.nii.gz" | wc -l)
  subfolder_count=$(find "$d" -type d -iname "sub-*" | wc -l)
  
  echo "  *t1w.nii.gz files: $t1w_count"
  echo "  sub-* folders:     $subfolder_count"
  echo
done
