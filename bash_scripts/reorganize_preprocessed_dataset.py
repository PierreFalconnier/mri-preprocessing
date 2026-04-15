import os
from argparse import ArgumentParser

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--source", required=True, help="Source root directory")
    parser.add_argument(
        "--destination", required=True, help="Destination root directory"
    )
    args = parser.parse_args()

    source_root = args.source
    destination_root = args.destination

    for dirpath, dirnames, filenames in os.walk(source_root):
        if os.path.basename(dirpath) == "anat":
            for subdir in dirnames:
                subdir_path = os.path.join(dirpath, subdir)

                if not os.path.isdir(subdir_path):
                    continue

                prefix = subdir  # e.g. sub-3055_ses-..._T1w

                # recreate anat folder in destination
                rel_path = os.path.relpath(dirpath, source_root)
                dest_anat = os.path.join(destination_root, rel_path)
                os.makedirs(dest_anat, exist_ok=True)

                for fname in os.listdir(subdir_path):
                    src = os.path.join(subdir_path, fname)

                    if os.path.isfile(src):
                        new_name = f"{prefix}_{fname}"
                        dst = os.path.join(dest_anat, new_name)

                        if os.path.exists(dst):
                            print(f"⚠️ Skipping (exists): {dst}")
                            continue

                        os.symlink(src, dst)
                        print(f"🔗 {dst} -> {src}")
