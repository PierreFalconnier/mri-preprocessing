find . -type f -name "*_18Feb2026.csv" -exec bash -c '
for f; do
  mv "$f" "${f/_18Feb2026/}"
done
' bash {} +
