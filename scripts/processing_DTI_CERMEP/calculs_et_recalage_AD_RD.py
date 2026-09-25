import os
import subprocess
import shutil
import time
import argparse

# === Argument parser ===
parser = argparse.ArgumentParser(description="Compute and register AD/RD/MD/FA maps from DWI data")
parser.add_argument("--lambda_dir", required=True, help="Path to lambdas")
parser.add_argument("--anat_dir", required=True, help="Path to anatomical derivatives (e.g. T1w)")
parser.add_argument("--dwi_dir", required=True, help="Path to DWI derivatives (eddy corrected etc.)")
parser.add_argument("--output_dir", required=True, help="Path to save the resulting metrics (AD, RD, etc.)")
args = parser.parse_args()

# === Directories from args ===
LAMBDA_DIR = args.lambda_dir
ANAT_DIR = args.anat_dir
DWI_DIR = args.dwi_dir
OUTPUT_DIR = args.output_dir

# === File templates ===
L1_TEMPLATE = "sub-{NOM}_ses-1_dir-PA_desc-eddy-topup_L1.nii.gz"
L2_TEMPLATE = "sub-{NOM}_ses-1_dir-PA_desc-eddy-topup_L2.nii.gz"
L3_TEMPLATE = "sub-{NOM}_ses-1_dir-PA_desc-eddy-topup_L3.nii.gz"
FA_TEMPLATE = "sub-{NOM}_ses-1_dir-PA_desc-eddy-topup_FA.nii.gz"

AD_OUTPUT_TEMPLATE = "sub-{NOM}_AD.nii.gz"
RD_OUTPUT_TEMPLATE = "sub-{NOM}_RD.nii.gz"
MD_OUTPUT_TEMPLATE = "sub-{NOM}_MD.nii.gz"
FA_OUTPUT_TEMPLATE = "sub-{NOM}_FA.nii.gz"

T1_TEMPLATE = "{sub_name}_ses-1_T1w_brain.nii.gz"
DWI_TEMPLATES = ["{sub_name}_ses-1_dir-PA_desc-eddy-topup_dwi.nii.gz", "{sub_name}_ses-1_dir-PA_desc-eddy-gre_dwi.nii.gz"]

ORIG_T1_TEMPLATE = "{sub_name}_orig_t1.nii.gz"
ORIG_DWI_TEMPLATE = "{sub_name}_orig_dwi.nii.gz"

T1_DWIspc_TEMPLATE = "t1_dwispc.nii.gz"
T1_DWIspc_MASKED_TEMPLATE = "t1_dwispc_masked.nii.gz"
T1_DWIspc_MASKED_BACK2T1spc_TEMPLATE = "t1_dwispc_masked_back2t1spc.nii.gz"

T1_TO_DWI_MAT_TEMPLATE = "t1_to_dwi.mat"
DWI_TO_T1_MAT_TEMPLATE = "dwi_to_t1.mat"

METRIC_TEMPLATE = ["AD", "RD", "MD", "FA"]




# Parcourir les sous-dossiers
for sub_dir in os.listdir(OUTPUT_DIR):
    sub_path = os.path.join(OUTPUT_DIR, sub_dir)
    
    if os.path.isdir(sub_path):
        # Extraire le NOM du sous-dossier
        NOM = sub_dir.split('-')[1]

        # Chemins des images à traiter
        L1_img = os.path.join(LAMBDA_DIR, f"sub-{NOM}", f"ses-1/{L1_TEMPLATE.format(NOM=NOM)}")
        L2_img = os.path.join(LAMBDA_DIR, f"sub-{NOM}", f"ses-1/{L2_TEMPLATE.format(NOM=NOM)}")
        L3_img = os.path.join(LAMBDA_DIR, f"sub-{NOM}", f"ses-1/{L3_TEMPLATE.format(NOM=NOM)}")
        FA_img = os.path.join(LAMBDA_DIR, f"sub-{NOM}", f"ses-1/{FA_TEMPLATE.format(NOM=NOM)}")

        # Vérification et tentative de correction des fichiers manquants
        missing_files = []
        for i, img in enumerate([L1_img, L2_img, L3_img, FA_img]):
            if not os.path.exists(img):
                new_img = img.replace('eddy-topup', 'eddy-gre')
                if os.path.exists(new_img):
                    if i == 0:
                        L1_img = new_img
                    elif i == 1:
                        L2_img = new_img
                    elif i == 2:
                        L3_img = new_img
                    elif i == 3:
                        FA_img = new_img
                else:
                    missing_files.append(img)

        # Si des fichiers sont toujours manquants, afficher une erreur et passer au sujet suivant
        if missing_files:
            print(f"Error: the following files are missing for {NOM} :")
            for file in missing_files:
                print(f"   - {file}")
            print("Next subject...\n")
            continue  # Passer directement au sujet suivant

        # Vérification que les images appartiennent bien au bon sujet
        for img in [L1_img, L2_img, L3_img, FA_img]:
            extracted_nom = os.path.basename(img).split('_')[0].replace("sub-", "")
            if extracted_nom != NOM:
                print(f"Careful: the image {img} does not corespond to {NOM} (trouvé {extracted_nom})")
                continue  # Passer au sujet suivant

        # Chemins des fichiers de sortie
        output_paths = {
            'AD': os.path.join(OUTPUT_DIR, f"sub-{NOM}", AD_OUTPUT_TEMPLATE.format(NOM=NOM)),
            'RD': os.path.join(OUTPUT_DIR, f"sub-{NOM}", RD_OUTPUT_TEMPLATE.format(NOM=NOM)),
            'MD': os.path.join(OUTPUT_DIR, f"sub-{NOM}", MD_OUTPUT_TEMPLATE.format(NOM=NOM)),
            'FA': os.path.join(OUTPUT_DIR, f"sub-{NOM}", FA_OUTPUT_TEMPLATE.format(NOM=NOM)),
        }

        # Vérification préalable des fichiers existants
        if all(os.path.exists(p) for p in output_paths.values()):
            print(f"Images for {NOM} already exists")
            continue

        # Création des fichiers AD, RD, et MD et FA avec subprocess
        try:
            subprocess.run(f"fslmaths {L2_img} -add {L3_img} -mul 0.5 {output_paths['RD']}", shell=True, check=True)
            subprocess.run(f"fslmaths {L1_img} {output_paths['AD']}", shell=True, check=True)
            subprocess.run(f"fslmaths {L1_img} -add {L2_img} -add {L3_img} -mul 0.333 {output_paths['MD']}", shell=True, check=True)
            subprocess.run(f"fslmaths {FA_img} {output_paths['FA']}", shell=True, check=True)
            print(f"Done for {NOM}: AD, RD, MD and FA images saved.")
        except subprocess.CalledProcessError as e:
            print(f"Error processing {NOM}: {str(e)}")
            continue

        # Traitement des fichiers T1 et DWI
        try:
            source_t1 = os.path.join(ANAT_DIR, sub_dir, "ses-1", T1_TEMPLATE.format(sub_name=sub_dir))
            dwi_files = [os.path.join(DWI_DIR, sub_dir, "ses-1", template.format(sub_name=sub_dir)) for template in DWI_TEMPLATES]
            
            source_dwi = next((dwi for dwi in dwi_files if os.path.exists(dwi)), None)
            
            if not source_dwi:
                print(f"Error: DWI not found for {sub_dir}")
                continue
            
            if not os.path.exists(sub_path):
                print(f"Error: Subject folder {sub_path} does not exist!")
                continue
            
            t1_orig = os.path.join(sub_path, ORIG_T1_TEMPLATE.format(sub_name=sub_dir))
            dwi_orig = os.path.join(sub_path, ORIG_DWI_TEMPLATE.format(sub_name=sub_dir))
            
            shutil.copy(source_t1, os.path.join(sub_path, T1_TEMPLATE.format(sub_name=sub_dir)))
            shutil.copy(source_dwi, os.path.join(sub_path, DWI_TEMPLATES[0].format(sub_name=sub_dir)))
            shutil.copy(source_t1, t1_orig)
            shutil.copy(source_dwi, dwi_orig)
            
            time.sleep(2)
            
            t1_dwispc = os.path.join(sub_path, T1_DWIspc_TEMPLATE)
            t1_to_dwi_mat = os.path.join(sub_path, T1_TO_DWI_MAT_TEMPLATE)
            subprocess.run(["flirt", "-in", source_t1, "-ref", dwi_orig, "-out", t1_dwispc, "-omat", t1_to_dwi_mat, "-dof", "6"], check=True)
            
            t1_dwispc_masked = os.path.join(sub_path, T1_DWIspc_MASKED_TEMPLATE)
            subprocess.run(["fslmaths", t1_dwispc, "-bin", t1_dwispc_masked], check=True)
            
            t1_dwispc_masked_back2t1spc = os.path.join(sub_path, T1_DWIspc_MASKED_BACK2T1spc_TEMPLATE)
            dwi_to_t1_mat = os.path.join(sub_path, DWI_TO_T1_MAT_TEMPLATE)
            subprocess.run(["flirt", "-in", t1_dwispc_masked, "-ref", t1_orig, "-out", t1_dwispc_masked_back2t1spc, "-omat", dwi_to_t1_mat, "-dof", "6"], check=True)
            
            for metric in METRIC_TEMPLATE:
                metric_file = os.path.join(sub_path, f"{sub_dir}_{metric}.nii.gz")
                metric_masked = os.path.join(sub_path, f"{sub_dir}_{metric}_masked.nii.gz")
                subprocess.run(["fslmaths", metric_file, "-mas", t1_dwispc_masked, metric_masked], check=True)
                
                metric_t1spc = os.path.join(sub_path, f"{sub_dir}_{metric}_masked_t1spc.nii.gz")
                subprocess.run(["flirt", "-in", metric_masked, "-ref", t1_orig, "-out", metric_t1spc, "-applyxfm", "-init", dwi_to_t1_mat], check=True)
                subprocess.run(["fslmaths", metric_t1spc, "-thr", "0", metric_t1spc], check=True)
            
            # Clean up unnecessary files
            for file in os.listdir(sub_path):
                if file not in [f"{sub_dir}_{metric}_masked_t1spc.nii.gz" for metric in METRIC_TEMPLATE]:
                    os.remove(os.path.join(sub_path, file))
            
            print(f"Done for {sub_dir}: masked images and registration saved.")
            
        except Exception as e:
            print(f"Bug for {sub_dir}: {str(e)} \n")

