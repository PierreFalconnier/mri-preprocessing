# FROM DOWNLOADING THE DATA TO TRAINING READY


1. **Create a collection** on ida.loni with advanced research, or **explore in depth using the obtained csv** from the image research results and other metadata csv to extract the wanted image ids

mri-preprocessing/csv_exploration/PPMI_explo/PPMI_utlimate_exploration.ipynb


2. **Download** as 10 compressed files using a download manager like jdownloader 2. Then **extract and merge** them all. Each folder is subject (eg "16")/sequence (eg "MPRAGE_ADNI_confirmed")/session(actually the date of the session, eg "2007-06-22_11_25_43.0")/image id (eg "I134760")/ all the dicoms (eg "AIBL_5_MR_MPRAGE_ADNI_confirmed__br_raw_20090128144239244_4_S62407_I134760.dcm")
bash_scripts/ida_merge_extract_all.sh (not really necessary, can do this manually in file manager)

3. **Flatten** this, meaning organize as sub-*/ses-YYYYMMDD/sequence/dcm files so the organization is nice to convert to bids
 
bash_scripts/ida_flatten.sh

4. **Organize as BIDS** and convert dcm to nii.gz, either using BIDScoin with appropriate configuration (.bidscoin/4.6.2/templates and the main CLI commands 'bidsmapper -t template_name sourcefolder bidsfolder' and 'bidscoiner sourcefolder bidsfolder'), or an existing tool like clinica, or a custom python script like i did for PPMI. Conversion from dcm to nii.gz is done with dcm2niix

mri-preprocessing/PPMI_to_bids/ppmi_to_bids.py (based on csv exploration results and pattern recognition)


5. **Preprocess the T1w** on the cluster using turboprep run_turboprep_jobs.sh, give it <SRC_DIR> <DST_DIR> <NUM_JOBS> <TURBO_PREP_PBS>
The transfert to the cluster can be done with a command like rsync -avhL --partial --info=progress2 --exclude="*foo.txt" source_folder destination_folder/
The bash script launch many jobs in parallel, the PBS file is used to ask a job and run the python script turboprep-multiple-v2.py
This python script takes as input a list of input image paths, the corresponding output path, and the MNI template to use. Use the  MNI152_T1_1mm_brain_RAS.nii.gz which is the template from fsl/data/standard/MNI152_T1_1mm_brain.nii.gz that as been reoriented to the RAS more conventional orientation, so that the preprocessed images are also RAS

mri-preprocessing/preprocessing/run_turboprep_jobs.sh

mri-preprocessing/preprocessing/turboprep-multiple-v2.py

6. **Reorganize the preprocessed dataset**
After preprocessing, the dataset looks like BIDS_datasets_selection_v2_processed/AABC_bids/sub-HCA6000030/ses-V1/anat/sub-HCA6000030_ses-V1_T1w/brain.nii.gz
Run the python script to reorganize as BIDS_datasets_selection_v2_processed/AABC_bids/sub-HCA6000030/ses-V1/anat/sub-HCA6000030_ses-V1_T1w_brain.nii.gz

mri-preprocessing/bash_scripts/reorganize_preprocessed_dataset.py

7. **Quality control**, use the following pbs, that will lauch qc_advanced_v2.py. The script takes as input the source dataset path, the mni template path MNI152_T1_1mm_brain_RAS.nii.gz, an output path for the csv and the output folder location
It computes metrics (saved in the csv, and in html for visualisation) and detect outliers, and create symbolic links to the destination folder, selecting only retained images

mri-preprocessing/quality_control/run_qc_job.pbs

See also submit_all_qc.sh

8. Given the curated dataset and patterns, **final preprocessing** that, orient to RAS, crop background based on minimal value and save as npy the volume, at the same location as the source nii.gz files but with .npy extension
mri-preprocessing/bash_scripts/add_npy_from_nii.py
