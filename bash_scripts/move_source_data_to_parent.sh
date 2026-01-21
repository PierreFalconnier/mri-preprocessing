find . -type d -name "sourcedata" -depth -exec bash -c '
  for d in "$@"; do
    parent=$(dirname "$d")
    mv "$d"/* "$parent"/
  done
' _ {} +
