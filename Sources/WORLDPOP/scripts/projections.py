import pandas as pd
import glob
import numpy as np
from sklearn.linear_model import LinearRegression
import os
path = os.getcwd()+"/Sources/WORLDPOP/"
print(path)
import sys
global projected_variable
projected_variable = sys.argv[1]


def flatten(l):
    return [item for sublist in l for item in sublist]

files = glob.glob(path+'data/worldpopstats_*.csv')
dfs = []
for file in files:
    print("file: "+ file)
    df = pd.read_csv(file)
    # Drop duplicate _x columns
    df = df.drop(columns=[c for c in df.columns if c.endswith('_x')], errors='ignore')
    df['year'] = int(file.split('_')[-1][:-4])
    dfs.append(df)

master_df = pd.concat(dfs)
master_df = master_df.sort_values(by='year').reset_index(drop=True)

# Define a function to extrapolate population
def extrapolate_variable(rc_data):
    # Drop NaN values before fitting
    rc_data = rc_data.dropna(subset=[projected_variable])

    # Need at least 2 data points to fit
    if len(rc_data) < 2:
        return [np.nan] * 6

    years = np.array(rc_data['year'].tolist())
    values = np.array(rc_data[projected_variable].tolist())

    years = years.reshape(-1, 1)
    values = values.reshape(-1, 1)

    model = LinearRegression()
    model.fit(years, values)

    projection_years = np.array([2021, 2022, 2023, 2024, 2025, 2026])
    projection_years = projection_years.reshape(-1, 1)

    projected_values = model.predict(projection_years)
    return flatten(projected_values)

# Group the data by object_id and apply the extrapolation function
extrapolated_data = master_df.groupby('object_id').apply(
    extrapolate_variable, include_groups=False
)

# Create a new DataFrame from the extrapolated data
extrapolated_df = pd.DataFrame(
    extrapolated_data.tolist(), 
    columns=['2021', '2022', '2023', '2024', '2025', '2026']
)
extrapolated_df.index = extrapolated_data.index
extrapolated_df = extrapolated_df.reset_index()

extrapolated_df = pd.melt(
    extrapolated_df, 
    id_vars=['object_id'], 
    var_name='year', 
    value_name=projected_variable
)

extrapolated_df.to_csv(path+'data/'+projected_variable+'_projections.csv', index=False)
print(f"Done! Saved to {path}data/{projected_variable}_projections.csv")
print(f"Shape: {extrapolated_df.shape}")