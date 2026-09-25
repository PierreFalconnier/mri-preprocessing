#!/bin/bash

## README ##

# This script BIDSifies the data of the study

# General structure
#├── README
#├── dataset_description.json
#├── participants.json
#├── participants.tsv
#├── .bidsignore
#├── sub-0001
#    └── ses-1
#    	 └── anat
#    	 └── func
#    	 └── fmap
#    	 └── dwi
#    	 └── pet
#    └── ses-2
#    	 └── anat
#    	 └── func
#    	 └── fmap
#    	 └── dwi
#├── derivatives
#├── sourcedata
#    └── Sequence_parameters.pdf
#    └── PET_reconstruction_parameters.txt
#    └── sub-0001
#	 └── ses-1
#            └──  DICOM
#                └── MRI
#                └── PET
#            ├── RAWDATA
#	 └── ses-2
#            └──  DICOM
#                └── MRI
#├── code


## PARAMETERS TO BE SET ## 

# Subject list
# CONTROLS IRM-TEP
#SUBJNAMES=(BJ11041 BT11058 VL10726 BI11106 TD11174 GC11271 RE11523 GF11719 GC11792 LV11811) 
# CONTROLS IRM seule
#SUBJNAMES=(TJ11714 GC11718 GR11802 BM11815 PD11834 LC07173 TC10358 VL12045 CB11673 CE12178 PF12203 GC12253 FN01312 CR12266 RN12296)
# PATIENTS CHRONICS
#SUBJNAMES=(MF10319 KM11362 LP11524 CL12106)
# PATIENTS SUB-AIGUS
#SUBJNAMES=(MM11697 MA11708 DA11953 GA12134 FP12224)
# PATIENTS
#SUBJNAMES=((LAIGI07087 ELABA07301 LAYCH07370 VINTH07401 GAUUL07407 PERPA07438 AYNSI07470 GAYFR07495 BADKA07504 BENCH07535 DELPH07541 PAIJO07564 FELNO07581 DURMO07595 MOLGU07704 COLSE07765 COUJE07810 CHAAB07833 WOLET07840 GACAL07845 LATFA07940 GROMA07996 LEVIS08057 CAPLE08130 BARPH08187 PICFL08202 DAVAN08240 THOTH08365 VILMA08560 NESKA08577 PICGA08615 MH09586 FT09679 PL09870 AC09910 BT10021 RS10191 CM10250 RS10272 AJ10477 VS10506 EM10512 EM10518 NN10771 GY10778 BS10780 PM10845 DO10898 AK10902 AJ10923 GY10986 BM11029 HM11036 AD11059 SK11073 VG11102 MJ11133 RJ11136 SB11414 BF11539 PA11557 GK11660 MM11700 LX11720 SO11859 SV11900 RD11934 EA11945 MP11963 GM12051 AM12174)

SUBJNAMES=(MF10319 KM11362 LP11524 CL12106 MM11697 MA11708 DA11953 GA12134 FP12224)

#SESSIONS=(1 2)
SESSIONS=(1)
#SESSIONS=(2)

# Paths
STUDY_PATH=/home/archive_lili/LILI/GOBERT_ETIC_IMAGINA/BIDS

# Image names
T1w=T1_MPRAGE_SAG
T2w=T2_TSE_TRA
T2star=T2_STAR_TRA
FLAIR=T2_SPACE_FLAIR_SAG
SWI=SWI_IMAGES
a_tof=TOF_3D_CRANE

rest_run_1_bold=EP2D_RSFMRI_PA
rest_run_2_bold=EP2D_RSFMRI_2_PA

# dwi depends on the session number and are set into the ses loop
b0_AP=EP2D_DTI_B0_2ISO_AP
gre_1=GRE_FIELD_MAPPING_1
gre_2=GRE_FIELD_MAPPING_2

ASL=EP2D_PCASL_PA
ASL_M0=EP2D_PCASL_M0_PA

pet_dyn=PET_DATA_MaxProb_DB2
pet_stat=PET_DATA_STAT_45_75_MaxProb_DB2


## END OF PARAMETERS TO BE SET


# Iterate accros subjects
for sub in ${SUBJNAMES[@]}
do
	for ses in ${SESSIONS[@]}
	do
		# Set variables
		sub_path=${STUDY_PATH}/sub-${sub}/ses-${ses} # sub_path includes session subfolder
		DICOM_MRI=${STUDY_PATH}/sourcedata/sub-${sub}/ses-${ses}/DICOM/MRI
		DICOM_PET=${STUDY_PATH}/sourcedata/sub-${sub}/ses-1/DICOM/PET
		
		# Create subfolders per modality
		mkdir -p $sub_path/anat
		mkdir -p $sub_path/func
		mkdir -p $sub_path/fmap
		mkdir -p $sub_path/dwi
		mkdir -p $sub_path/perf

		if [ $ses == 1 ]; then
			mkdir -p $sub_path/pet
			dwi=EP2D_DTI_64DIR_2ISO_PA
		fi
		if [ $ses == 2 ]; then
			dwi=EP2D_DTI_64DIR_2ISO_7B0_PA
		fi

		# Convert anatomical data
		if [ ! -e ${sub_path}/anat/sub-${sub}_ses-${ses}_T1w.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/anat/ -f sub-${sub}_ses-${ses}_T1w ${DICOM_MRI}/$T1w
		fi
		if [ ! -e ${sub_path}/anat/sub-${sub}_ses-${ses}_T2w.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/anat/ -f sub-${sub}_ses-${ses}_T2w ${DICOM_MRI}/$T2w
		fi
		if [ ! -e ${sub_path}/anat/sub-${sub}_ses-${ses}_T2star.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/anat/ -f sub-${sub}_ses-${ses}_T2star ${DICOM_MRI}/$T2star
		fi
		if [ ! -e ${sub_path}/anat/sub-${sub}_ses-${ses}_FLAIR.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/anat/ -f sub-${sub}_ses-${ses}_FLAIR ${DICOM_MRI}/$FLAIR
		fi
		if [ ! -e ${sub_path}/anat/sub-${sub}_ses-${ses}_SWI.nii.gz ]; then
                        dcm2niix -m y -z y -b y -o ${sub_path}/anat/ -f sub-${sub}_ses-${ses}_SWI ${DICOM_MRI}/$SWI
                fi
		if [ ! -e ${sub_path}/anat/sub-${sub}_ses-${ses}_aTOF.nii.gz ] && [ -e ${DICOM_MRI}/$a_tof ] ; then
                        dcm2niix -m y -z y -b y -o ${sub_path}/anat/ -f sub-${sub}_ses-${ses}_aTOF ${DICOM_MRI}/$a_tof
                fi


		# Convert resting state data
		if [ ! -e ${sub_path}/func/sub-${sub}_ses-${ses}_task-rest_run-1_bold.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/func/ -f sub-${sub}_ses-${ses}_task-rest_run-1_bold ${DICOM_MRI}/$rest_run_1_bold
		fi
		if [ $ses == 1 ] && [ ! -e ${sub_path}/func/sub-${sub}_ses-${ses}_task-rest_run-2_bold.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/func/ -f sub-${sub}_ses-${ses}_task-rest_run-2_bold ${DICOM_MRI}/$rest_run_2_bold
		fi
		# Convert diffusion data
       	 	if [ ! -e ${sub_path}/dwi/sub-${sub}_ses-${ses}_dir-PA_dwi.nii.gz ]; then
       	 	        dcm2niix -m y -z y -b y -o ${sub_path}/dwi/ -f sub-${sub}_ses-${ses}_dir-PA_dwi ${DICOM_MRI}/$dwi
       	 	fi

		# Convert fmap data 
		if [ -e ${DICOM_MRI}/${gre_1} ] && [ ! -e ${sub_path}/fmap/sub-${sub}_ses-${ses}_magnitude.nii.gz ]; then
       			dcm2niix -m y -z y -b y -o ${sub_path}/fmap/ -f sub-${sub}_ses-${ses}_magnitude --terse ${DICOM_MRI}/${gre_1} 
			#mv ${sub_path}/fmap/sub-${sub}_ses-${ses}_magnitude_e2.nii.gz ${sub_path}/fmap/sub-${sub}_ses-${ses}_magnitude.nii.gz
			#mv ${sub_path}/fmap/sub-${sub}_ses-${ses}_magnitude_e2.json ${sub_path}/fmap/sub-${sub}_ses-${ses}_magnitude.json
		fi
		if [ -e ${DICOM_MRI}/${gre_2} ] && [ ! -e ${sub_path}/fmap/sub-${sub}_ses-${ses}_phasediff.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/fmap/ -f sub-${sub}_ses-${ses}_phasediff --terse ${DICOM_MRI}/${gre_2} 
			#mv ${sub_path}/fmap/sub-${sub}_ses-${ses}_phasediff_e2.nii.gz ${sub_path}/fmap/sub-${sub}_ses-${ses}_phasediff.nii.gz
			#mv ${sub_path}/fmap/sub-${sub}_ses-${ses}_phasediff_e2.json ${sub_path}/fmap/sub-${sub}_ses-${ses}_phasediff.json
		fi
		if [ -e ${DICOM_MRI}/$b0_AP ] && [ ! -e ${sub_path}/fmap/sub-${sub}_ses-${ses}_dir-AP_epi.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/fmap/ -f sub-${sub}_ses-${ses}_dir-AP_epi ${DICOM_MRI}/$b0_AP
		fi

		# Convert ASL
        	if [ ! -e ${sub_path}/perf/sub-${sub}_ses-${ses}_asl.nii.gz ]; then 
        	        dcm2niix -m y -z y -b y -o ${sub_path}/perf/ -f sub-${sub}_ses-${ses}_asl ${DICOM_MRI}/$ASL
        	        dcm2niix -m y -z y -b y -o ${sub_path}/perf/ -f sub-${sub}_ses-${ses}_m0scan ${DICOM_MRI}/$ASL_M0 # not applicable in this study
        	fi 

		# Convert PET data
		if [ $ses == 1 ] && [ ! -e ${sub_path}/pet/sub-${sub}_ses-${ses}_rec-acdyn_pet.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/pet/ -f sub-${sub}_ses-${ses}_rec-acdyn_pet ${DICOM_PET}/$pet_dyn
		fi
		if [ $ses == 1 ] && [ ! -e ${sub_path}/pet/sub-${sub}_ses-${ses}_rec-acstat_pet.nii.gz ]; then
			dcm2niix -m y -z y -b y -o ${sub_path}/pet/ -f sub-${sub}_ses-${ses}_rec-acstat_pet ${DICOM_PET}/$pet_stat
		fi

		# Copy AIF data
		if [ $ses == 1 ] && [ ! -e ${sub_path}/pet/sub-${sub}_ses-1_recording-manual_blood.json ]; then
                
        		cp $STUDY_PATH/sourcedata/sub-${sub}/ses-1/AIF/sub-${sub}_ses-1_Ca.txt ${sub_path}/pet/.
        		cp $STUDY_PATH/sourcedata/sub-${sub}/ses-1/AIF/sub-${sub}_ses-1_recording-manual_blood.tsv ${sub_path}/pet/.
        		cp $STUDY_PATH/sourcedata/sub-${sub}/ses-1/AIF/sub-${sub}_ses-1_blood.json ${sub_path}/pet/.
        		cp $STUDY_PATH/sourcedata/sub-${sub}/ses-1/AIF/sub-${sub}_ses-1_recording-manual_blood.json ${sub_path}/pet/.
		fi
	done
done

