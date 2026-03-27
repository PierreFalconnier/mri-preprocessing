
aws s3 sync --no-sign-request  \
                              --exclude "*MRI_Prepro*/*" \
                               --exclude "*func/*" \
                               --exclude "*dwi/*" \
                               --exclude "*fmap/*" \
                               --exclude "*perf/*" \
                               --exclude "*beh/*" \
                             --exclude "*T2w*" \
                             --exclude "*FLAIR*" \
                             --exclude "*derivatives/*" \
                             --exclude "*stimuli/*" \
                             --exclude "*swi/*"
