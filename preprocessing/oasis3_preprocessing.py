import shutil
import subprocess
from argparse import ArgumentParser
from pathlib import Path

import ants
import pandas as pd
from tqdm import tqdm


# ===========================================================
#  UTILITY: find T1w image path for subject/session
# ===========================================================
def find_t1w_image(subject_id, session_id, oasis3_data_dir):
    subject_dir = oasis3_data_dir / subject_id
    pattern = f"{subject_id}_{session_id}*T1w.nii.gz"
    # sort to select the first if multiple exist
    matches = sorted(list(subject_dir.rglob(pattern)))
    return matches[0] if matches else None


# ===========================================================
#  MAIN
# ===========================================================
if __name__ == "__main__":
    # ----------------------- ARGS ----------------------------
    aparser = ArgumentParser()
    aparser.add_argument(
        "--save_root",
        type=str,
        required=True,
        help="Output root folder for preprocessed data.",
    )
    args = aparser.parse_args()

    # ---------------------- PATHS ----------------------------
    root_dir = Path(__file__).parents[2]
    data_dir = root_dir / "data"
    oasis3_data_dir = data_dir / "OASIS3" / "raw"

    csv_path = oasis3_data_dir.parent / "mr_sessions_with_diag.csv"
    data_df = pd.read_csv(csv_path)

    save_root = Path(args.save_root)
    save_root.mkdir(exist_ok=True, parents=True)

    # MNI templates
    mni_template = ants.image_read(str(oasis3_data_dir.parent / "MNI152_T1_1mm.nii.gz"))
    mni_brain = ants.image_read(
        str(oasis3_data_dir.parent / "MNI152_T1_1mm_brain.nii.gz")
    )
    mni_mask = ants.image_read(
        str(oasis3_data_dir.parent / "MNI152_T1_1mm_brain_mask.nii.gz")
    )

    # ===========================================================
    #   PROCESS ALL SUBJECTS
    # ===========================================================
    subjects = sorted(data_df["subject_id"].unique())

    for subject_id in (pbar := tqdm(subjects)):
        pbar.set_description(f"Processing {subject_id}")

        subject_rows = data_df[data_df["subject_id"] == subject_id].sort_values(
            "session_id"
        )

        # Output folder
        subject_out = save_root / subject_id
        subject_out.mkdir(exist_ok=True)

        earliest_img = None

        # ========================================================
        #   PROCESS EACH SESSION
        # ========================================================
        for i, row in enumerate(subject_rows.itertuples()):
            session_id = row.session_id

            # Create session folder
            session_out = subject_out / session_id
            session_out.mkdir(exist_ok=True)

            # -------------------------------
            # Find T1w image
            # -------------------------------
            img_path = find_t1w_image(subject_id, session_id, oasis3_data_dir)
            if img_path is None:
                print(f"WARNING: No T1w image found for {subject_id}/{session_id}")
                continue

            # Copy raw image into the folder
            raw_copy_path = session_out / img_path.name
            shutil.copyfile(img_path, raw_copy_path)

            img = ants.image_read(str(raw_copy_path))
            img_basename = img_path.name.replace(".nii.gz", "")

            # ====================================================
            #  FIRST SESSION ONLY
            # ====================================================
            if i == 0:
                earliest_img = img

                imagedenoise = ants.denoise_image(img, ants.get_mask(img))
                # ants.plot(imagedenoise, axis=0)
                # ants.plot(imagedenoise, axis=1)
                # ants.plot(imagedenoise, axis=2)
                # mni_out = session_out / f"{img_basename}_denoise.nii.gz"
                # imagedenoise.image_write(str(mni_out))

                # -------------------------------
                # 1) Register full raw image to MNI
                # -------------------------------
                earliest_mni_reg = ants.registration(
                    fixed=mni_template,
                    moving=imagedenoise,  # raw full image
                    type_of_transform="Affine",
                )

                # Save warped image in MNI space + Save transform for later use
                mni_out = session_out / f"{img_basename}_MNI.nii.gz"
                earliest_mni_reg_img = earliest_mni_reg["warpedmovout"]
                earliest_mni_reg_img.image_write(str(mni_out))

                earliest_tx = session_out / f"{img_basename}_MNI.mat"
                shutil.copyfile(earliest_mni_reg["fwdtransforms"][0], earliest_tx)
                # -------------------------------
                # 2) Brain extraction on MNI-space image
                # remark : hd-bet add another _bet suffix for mask
                # -------------------------------
                bet_path = session_out / f"{img_basename}_MNI_bet.nii.gz"
                mask_path = session_out / f"{img_basename}_MNI_bet_bet.nii.gz"

                if mask_path.exists():
                    print(f"BET image already exists for {img_basename}, skipping BET.")
                else:
                    cmd = [
                        "hd-bet",
                        "-i",
                        str(raw_copy_path),
                        # str(mni_out),
                        "-o",
                        str(bet_path),
                        "-device",
                        "cpu",
                        "--disable_tta",
                        "--save_bet_mask",
                        "--no_bet_image",  # save space
                    ]
                    subprocess.run(cmd)

                # get mask image (brain only)
                if mask_path.exists():
                    earliest_mask = ants.image_read(str(mask_path))
                    # img_masked = ants.mask_image(earliest_mni_reg_img, earliest_mask)
                    img_masked = ants.mask_image(earliest_img, earliest_mask)

                else:
                    raise FileNotFoundError(f"No BET output found for {img_basename}")

                # -------------------------------
                # 3) N4 Bias field correction on brain-only image
                # Save final bias-corrected brain in MNI space
                # -------------------------------
                earliest_img_corr = ants.n4_bias_field_correction(img_masked)

                out_corr = session_out / f"{img_basename}_N4_in_MNI.nii.gz"
                earliest_img_corr.image_write(str(out_corr))

            # ====================================================
            #  FOLLOW-UP SESSIONS
            # ====================================================
            else:
                # -------------------------------
                # 1) Compute the Register trasform to earliest T1 (within-subject)
                # -------------------------------
                reg = ants.registration(
                    fixed=earliest_img,  # first session T1
                    moving=img,  # current follow-up T1
                    type_of_transform="Affine",  # OR RIGID ??
                )

                # -------------------------------
                # 2) Transform to MNI using Concatenated Transforms
                # -------------------------------
                # T_mni( T_earliest( image ) )
                # The list should be: [ Transform_to_MNI, Transform_to_Earliest ]
                combined_transforms = (
                    earliest_mni_reg["fwdtransforms"] + reg["fwdtransforms"]
                )

                img_mni = ants.apply_transforms(
                    fixed=mni_template,  # full MNI
                    moving=img,  #  ORIGINAL follow-up image
                    transformlist=combined_transforms,
                    interpolator="linear",
                )

                # -------------------------------
                # 3) Apply brain mask from first session (in MNI space)
                # -------------------------------
                img_brain = ants.mask_image(img_mni, earliest_mask)

                # -------------------------------
                # 4) N4 bias field correction on brain-only image
                # Save final bias-corrected brain in MNI space
                # -------------------------------
                img_corr = ants.n4_bias_field_correction(img_brain)

                out_corr = session_out / f"{img_basename}_N4_in_MNI.nii.gz"
                img_corr.image_write(str(out_corr))

    print("=== FINISHED ALL SUBJECTS ===")
