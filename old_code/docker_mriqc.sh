# sudo docker run -it --rm \
#                                -v /home/falconnier/Downloads/CamCAN:/data:ro \
#                                -v /home/falconnier/Documents/MRIQC_out:/out \
#                                nipreps/mriqc:latest \
#                                /data /out participant \
#                              --no-sub --modalities T1w -v


sudo docker run -it --rm \
    -v /home/falconnier/Downloads/CamCAN:/data:ro \
    -v /home/falconnier/Documents/MRIQC_out:/out \
    nipreps/mriqc:latest \
    /data /out participant \
    --participant-label CC110037 \
    --nprocs 8 \
    --mem 8 \
    --no-sub \
    --modalities T1w