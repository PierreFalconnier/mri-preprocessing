import re
from pathlib import Path

# Folder containing all subjects/sessions
bids_dir = Path(
    "/home/falconnier/Downloads/HABS/extracted/flattened /home/falconnier/Downloads/HABS/extracted/HABS_bids"
)

# Regex to remove control characters
ctrl_chars = re.compile(r"[\x00-\x1F]")

for jf in bids_dir.rglob("*.json"):
    with open(jf, "r", encoding="utf-8") as f:
        text = f.read()
    clean_text = ctrl_chars.sub("", text)
    with open(jf, "w", encoding="utf-8") as f:
        f.write(clean_text)
    print(f"Sanitized {jf}")
