import pandas as pd
import glob
from sklearn.linear_model import LinearRegression
import numpy as np
import os

# Base WORLDPOP path (from repo root)
path = os.getcwd() + "/Sources/WORLDPOP/"
print("WORLDPOP path:", path)

def flatten(l):
    """Flatten a list of lists into a single list."""
    return [item for sublist in l for item in sublist]

# -------------------------------------------------------------------
# 1. Read all worldpopstats_*.csv and add 'year' from filename
# -------------------------------------------------------------------
files = glob.glob(path + "data/worldpopstats_*.csv")
dfs = []

if not files:
    raise RuntimeError(f"No files found at {path+'data/worldpopstats_*.csv'}")

for file in files:
    print("file:", file)
    df = pd.read_csv(file)

    # Ensure the 3 variables exist (just a sanity check)
    expected_cols = [
        "mean_sex_ratio_y",
        "sum_aged_population_y",
        "sum_young_population_y",
        "object_id",
    ]
    for col in expected_cols:
        if col not in df.columns:
            raise KeyError(f"Column '{col}' not found in {file}")

    # Extract year from filename e.g. worldpopstats_2017.csv -> 2017
    year_from_name = int(os.path.basename(file).split("_")[-1][:-4])
    df["year"] = year_from_name

    # Keep only relevant columns plus 'year'
    df = df[
        [
            "object_id",
            "year",
            "mean_sex_ratio_y",
            "sum_aged_population_y",
            "sum_young_population_y",
        ]
    ]

    dfs.append(df)

# -------------------------------------------------------------------
# 2. Combine into a master dataframe
# -------------------------------------------------------------------
master_df = pd.concat(dfs, ignore_index=True)
master_df = master_df.sort_values(by="year").reset_index(drop=True)

# Convert variables to numeric (in case of stray strings)
for col in ["mean_sex_ratio_y", "sum_aged_population_y", "sum_young_population_y"]:
    master_df[col] = pd.to_numeric(master_df[col], errors="coerce")

# Projection years
projection_years = np.array([2021, 2022, 2023, 2024, 2025]).reshape(-1, 1)

# -------------------------------------------------------------------
# 3. Extrapolation function for one object_id and one variable
# -------------------------------------------------------------------
def extrapolate_variable_for_group(rc_data, var_name):
    """
    rc_data: dataframe for a single object_id across years
    var_name: one of 'mean_sex_ratio_y', 'sum_aged_population_y', 'sum_young_population_y'
    """
    # Keep rows where both year and the variable are non-null
    rc = rc_data[["year", var_name]].dropna()

    # If no valid values, fill projection with NaNs
    if rc.shape[0] == 0:
        return [np.nan] * len(projection_years)

    # If only one valid value, repeat it for all projection years
    if rc.shape[0] == 1:
        v = rc[var_name].iloc[0]
        return [v] * len(projection_years)

    years = rc["year"].to_numpy().reshape(-1, 1)
    values = rc[var_name].to_numpy().reshape(-1, 1)

    model = LinearRegression()
    model.fit(years, values)

    projected_values = model.predict(projection_years)
    return flatten(projected_values)

# -------------------------------------------------------------------
# 4. Project for the three variables and write three CSVs
# -------------------------------------------------------------------
variables_to_project = [
    ("mean_sex_ratio_y", "mean_sex_ratio_projections.csv"),
    ("sum_aged_population_y", "sum_aged_population_projections.csv"),
    ("sum_young_population_y", "sum_young_population_projections.csv"),
]

# (Optional) Print NaN counts so you know what's up
for var_name, _ in variables_to_project:
    print(f"NaNs in {var_name}: {master_df[var_name].isna().sum()}")

for var_name, output_filename in variables_to_project:
    print(f"Projecting variable: {var_name}")

    # Apply per object_id
    extrapolated_data = master_df.groupby("object_id").apply(
        lambda grp: extrapolate_variable_for_group(grp, var_name)
    )

    # Turn into DataFrame with year columns as wide format
    extrapolated_df = pd.DataFrame(
        extrapolated_data.tolist(),
        columns=["2021", "2022", "2023", "2024", "2025"],
    )

    # Bring object_id back as a column
    extrapolated_df.index = extrapolated_data.index
    extrapolated_df = extrapolated_df.reset_index()  # adds 'object_id'

    # Long format: object_id, year, <var_name>
    extrapolated_df = pd.melt(
        extrapolated_df,
        id_vars=["object_id"],
        var_name="year",
        value_name=var_name,
    )

    # Save file
    output_path = os.path.join(path, "data", output_filename)
    extrapolated_df.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")
