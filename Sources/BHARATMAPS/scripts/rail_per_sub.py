import geopandas as gpd
import pandas as pd
import os

repo_root = "/Users/stephensmathew/cdl_rep/flood-data-ecosystem-UP"

# Load rails and subdistrict data
rails_gdf = gpd.read_file(os.path.join(repo_root, "Sources/BHARATMAPS/data/Raw Data/rail_length_up.geojson"))
up_sub_gdf = gpd.read_file(os.path.join(repo_root, "Maps/up_ids-drr_shapefiles/UP_subdistrict_final_4326.geojson"))

# Matching CRS
rails_gdf = rails_gdf.to_crs(up_sub_gdf.crs)

# Spatial join: rails inside subdistricts
rails_in_up = gpd.sjoin(rails_gdf, up_sub_gdf, how="left", predicate="within")

# Inspect columns
print(rails_in_up.columns)

# Group by subdistrict and calculate total rail length and count of rail segments
rail_lengths_up = (
    rails_in_up.groupby("object_id_right").agg(
        total_rail_length=("LENGTH", "sum"),  # sum of rail lengths
        rail_count=("COUNT", "sum")        # number of rail segments
    ).reset_index()
    .rename(columns={"object_id_right": "object_id"})
)

# Save output
output_path = os.path.join(repo_root, "Sources/BHARATMAPS/data/variables/RailLengths/RailLengths.csv")
os.makedirs(os.path.dirname(output_path), exist_ok=True)
rail_lengths_up.to_csv(output_path, index=False)

print(f"✅ Total rail lengths and segment counts per subdistrict saved to: {output_path}")
