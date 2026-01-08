"""
script to remove the SMC patient from the ADNI csv
"""

import pandas as pd

input_file = "/home/falconnier/Documents/fe_med/data_folder/ADNI/data_original.csv"
output_file = "/home/falconnier/Documents/fe_med/data_folder/ADNI/data.csv"
df = pd.read_csv(input_file)
print(len(df))
df_filtered = df[df["Group"] != "SMC"]
print(len(df_filtered))

group_portions = df_filtered["Group"].value_counts(normalize=True) * 100

print(group_portions)

# df_filtered.to_csv(output_file, index=False)
