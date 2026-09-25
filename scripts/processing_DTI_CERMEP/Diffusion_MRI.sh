#!/bin/bash

## README ##

# This script pre-processes diffusion data with FSL tools and fits the DTI to generate FA and MD maps.
# First subjects do not have phase-reversed B0 image (B0_AP) and are precessed with the field map and the eddy function.
# The following sujects can benefit of topup function with B0 AP and PA images.

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

SESSIONS=(1) 
SUBJNAMES=(GC12253 FN01312 CR12266 RN1229)

### SESSION 1 ###

# Subjets without AP-PA map
#SUBJNAMES=(LAIGI07087 ELABA07301 LAYCH07370 VINTH07401 GAUUL07407 PERPA07438 AYNSI07470 GAYFR07495 BADKA07504 BENCH07535 DELPH07541 PAIJO07564 FELNO07581 DURMO07595 MOLGU07704 COLSE07765)

# Subjets with AP-PA map
#SUBJNAMES=(COUJE07810 CHAAB07833 WOLET07840 GACAL07845 LATFA07940 GROMA07996 LEVIS08057 CAPLE08130 BARPH08187 PICFL08202 DAVAN08240 THOTH08365 VILMA08560 NESKA08577 PICGA08615 MH09586 FT09679 PL09870 AC09910 BT10021 RS10191 CM10250 RS10272 AJ10477 VS10506 EM10512 EM10518 NN10771 GY10778 BS10780 PM10845 DO10898 AK10902 AJ10923 GY10986 BM11029 HM11036 AD11059 SK11073 VG11102 MJ11133 RJ11136 SB11414 BF11539 PA11557 GK11660 MM11700 LX11720 SO11859 SV11900 RD11934 EA11945 MP11963 GM12051 AM12174)

### SESSION 2 ###

# Subjets without AP-PA map
#SUBJNAMES=(ELABA07301 LAYCH07370 GAUUL07407 PERPA07438 AYNSI07470 BADKA07504 BENCH07535 DELPH07541 FELNO07581)

# Subjets with AP-PA map
#SUBJNAMES=(MOLGU07704 COLSE07765 CHAAB07833 WOLET07840 LATFA07940 GROMA07996 LEVIS08057 CAPLE08130 BARPH08187 PICFL08202 DAVAN08240 THOTH08365 NESKA08577 PICGA08615 MH09586 FT09679 PL09870 AC09910 BT10021 RS10191 RS10272 AJ10477 VS10506 EM10518 EM10512 NN10771 GY10778 BS10780 PM10845 AJ10923 GY10986 BM11029 HM11036 AD11059 SK11073 VG11102 MJ11133 RJ11136 SB11414 BF11539 PA11557 GK11660 MM11700 LX11720 SV11900 RD11934 EA11945 MP11963 GM12051 AM12174)

# Paths
STUDY_PATH=/home/archive_lili/LILI/GOBERT_ETIC_IMAGINA/BIDS
SRC=$STUDY_PATH/code
 
# Activate steps
PREPROCESSING_eddy_gre=0 # only done for the first patients that did not have AP-PA acquisition
PREPROCESSING_eddy_topup=1
SD_DWI=0
DTI_FIT=1
      
## END OF PARAMETERS TO BE SET
  

for sub in ${SUBJNAMES[@]}
do
for ses in ${SESSIONS[@]}
do
        echo -------------------------
        echo Processing DTI for sub-${sub}
        echo -------------------------

	# Define variables
        DATA_PATH=${STUDY_PATH}/derivatives/dwi/sub-${sub}/ses-${ses}
	bvecs=$STUDY_PATH/sub-${sub}/ses-${ses}/dwi/sub-${sub}_ses-${ses}_dir-PA_dwi.bvec
	bvals=$STUDY_PATH/sub-${sub}/ses-${ses}/dwi/sub-${sub}_ses-${ses}_dir-PA_dwi.bval

	#$STUDY_PATH/sub-${sub}_ses-${ses}/dwi/sub-${sub}_ses-${ses}_dir-PA_dwi
	#$STUDY_PATH/sub-${sub}_ses-${ses}/fmap/sub-${sub}_ses-${ses}_dir-AP_epi
	#$STUDY_PATH/sub-${sub}_ses-${ses}/fmap/sub-${sub}_ses-${ses}_magnitude
	#$STUDY_PATH/sub-${sub}_ses-${ses}/fmap/sub-${sub}_ses-${ses}_phasediff
	#${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_dwi
	#${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddygre_dwi
	#${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddytopup_dwi

        # Create output folder
        if [ ! -e ${DATA_PATH}/ ]; then
                mkdir -p ${DATA_PATH}
        fi

      	# Link orig data to derivarives folder 
        if [ ! -e $DATA_PATH/sub-${sub}_ses-${ses}_dir-PA_dwi.nii.gz ]; then
                ln -s $STUDY_PATH/sub-${sub}/ses-${ses}/dwi/sub-${sub}_ses-${ses}_dir-PA_dwi.nii.gz $DATA_PATH/.
		ln -s $STUDY_PATH/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_magnitude.nii.gz $DATA_PATH/.
		ln -s $STUDY_PATH/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_phasediff.nii.gz $DATA_PATH/.
		ln -s $STUDY_PATH/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_dir-AP_epi.nii.gz $DATA_PATH/.
        fi

	# Preprocessing with fieldmap (when AP-PA is not available)
	if [ $PREPROCESSING_eddy_gre -eq 1 ] && [ ! -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi.nii.gz ]; then
        	
		# Brain mask
        	fslroi ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_dwi.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_epi.nii.gz 0 1
        	bet2 ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_epi.nii ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_epi -m -n -f 0.6
		fslmaths ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_epi_mask.nii.gz -ero -bin ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_epi_desc-ero_mask.nii.gz
        	bet2 ${DATA_PATH}/sub-${sub}_ses-${ses}_magnitude.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-bet_magnitude

        	# Prepare filed map : scanner phase_image magnitude_image out_image deltaTE (deltaTe = 2.46 = TE diff in dual echo acquisition)
        	fsl_prepare_fieldmap SIEMENS ${DATA_PATH}/sub-${sub}_ses-${ses}_phasediff.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-bet_magnitude.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-rads_fmap.nii.gz 2.46

        	# Conversion to Hz (div 2*pi) and resampling to DTI resolution
        	fslmaths ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-rads_fmap.nii.gz -div 6.2832 ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-Hz_fmap.nii.gz
		reg_resample -ref ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_epi.nii.gz -flo ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-Hz_fmap.nii.gz -res ${DATA_PATH}/sub-${sub}_ses-${ses}_res-dwi_desc-Hz_fmap.nii.gz
        
		# Smooth field map to maske it inversible and avoid artefacts with eddy
		fslmaths ${DATA_PATH}/sub-${sub}_ses-${ses}_res-dwi_desc-Hz_fmap.nii.gz -s 4 ${DATA_PATH}/sub-${sub}_ses-${ses}_res-dwi_desc-Hz-smoothed_fmap.nii.gz

		# Eddy: for Eddy currents + magnetic susceptibility  (filed map smoothed)
       		eddy --imain=${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_dwi.nii.gz --mask=${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_epi_desc-ero_mask --index=$SRC/DTI_index_ses-${ses}.txt --acqp=$SRC/DTI_acqp.txt --bvecs=${bvecs} --bvals=${bvals} --out=${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi --field=${DATA_PATH}/sub-${sub}_ses-${ses}_res-dwi_desc-Hz-smoothed_fmap
		
	fi # end PREPROCESSING


	#PREPROCESSING_eddy_topup
	if [ $PREPROCESSING_eddy_topup -eq 1 ] && [ ! -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi.nii.gz ]; then

		# Split vol B0
		fslroi ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_dwi.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_epi.nii.gz 0 1
		        
		# topup : magnetic susceptibility correction
		fslmerge -t ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PAAP_epi.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_epi.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-AP_epi.nii.gz
		topup --imain=${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PAAP_epi.nii.gz --datain=$SRC/DTI_acqp_topup.txt --out=${DATA_PATH}/sub-${sub}_ses-${ses}_topup_results --iout=${DATA_PATH}/sub-${sub}_ses-${ses}_desc-moco

		# Create mask from non-distorted data
		fslmaths ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-moco.nii.gz -Tmean ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-moco-mean.nii.gz
		bet2 ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-moco-mean.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-moco-mean -m -n -f 0.6
		                
		# eddy + topup : Eddy currents + magnetic susceptibility correction (from AP-PA series)
		eddy --imain=${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_dwi.nii.gz --mask=${DATA_PATH}/sub-${sub}_ses-${ses}_desc-moco-mean_mask.nii.gz --index=$SRC/DTI_index_ses-${ses}.txt --acqp=$SRC/DTI_acqp.txt --bvecs=${bvecs} --bvals=${bvals} --topup=${DATA_PATH}/sub-${sub}_ses-${ses}_topup_results --out=${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi
		     
	fi # end PREPROCESSING


	# Check corrections with SD
	if [ $SD_DWI -eq 1 ]; then

		if [[ -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi.nii.gz ]] && [[ ! -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi_SD.nii.gz ]]; then
			fslroi ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi_DWI 1 65
                        fslmaths ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi_DWI.nii.gz -Tstd ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi_SD
			rm ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi_DWI.nii.gz
		fi

		if [[ -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi.nii.gz ]] && [[ ! -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi_SD.nii.gz ]]; then
			fslroi ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi_DWI 1 65
			fslmaths ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi_DWI.nii.gz -Tstd ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi_SD
			rm ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi_DWI.nii.gz
		fi
	fi # end SD_DWI


	# Simple DTI fit (generates FA maps) 
        if [ $DTI_FIT -eq 1 ]; then	

		if [[ -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi.nii.gz ]] && [[ ! -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_FA.nii.gz ]]; then
			bet2 ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_epi -m -n -f 0.2
			fslmaths ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_epi_mask.nii.gz -ero -bin ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre-ero_epi_mask.nii.gz
        		dtifit -k ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi.nii.gz -o ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre -m ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre-ero_epi_mask.nii.gz -b ${bvals} -r ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_dwi.eddy_rotated_bvecs
			rm ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre-ero_epi_mask.nii.gz ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-gre_epi_mask.nii.gz
		fi

		if [[ -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi.nii.gz ]] && [[ ! -e ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_FA.nii.gz ]]; then
			dtifit -k ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi.nii.gz -o ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup -m ${DATA_PATH}/sub-${sub}_ses-${ses}_desc-moco-mean  -b ${bvals} -r ${DATA_PATH}/sub-${sub}_ses-${ses}_dir-PA_desc-eddy-topup_dwi.eddy_rotated_bvecs
		fi

       	fi # end DTI_FIT

done # fin boucle sessions
done #fin boucle sujets
exit
