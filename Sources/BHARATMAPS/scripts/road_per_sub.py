import geopandas as gpd
import pandas as pd
import os

repo_root = "/Users/stephensmathew/cdl_rep/flood-data-ecosystem-UP"

# Load road length data and UP subdistrict shapefile
road_path = os.path.join(repo_root, "Sources/BHARATMAPS/data/Raw Data/merged_roads_up_length.geojson")
subdistrict_path = os.path.join(repo_root, "Maps/up_ids-drr_shapefiles/UP_subdistrict_final_4326.geojson")

road_gdf = gpd.read_file(road_path)
up_sub_gdf = gpd.read_file(subdistrict_path)

# Align CRS
road_gdf = road_gdf.to_crs(up_sub_gdf.crs)

# Spatial join: roads inside subdistricts
roads_in_up = gpd.sjoin(road_gdf, up_sub_gdf, how="left", predicate="within")

# Inspect columns
print(roads_in_up.columns)

# Group by subdistrict and calculate total road length only
road_lengths_up = (
    roads_in_up.groupby("object_id_right")["LENGTH"]
    .sum()
    .reset_index()
    .rename(columns={"object_id_right": "object_id", "LENGTH": "total_road_length"})
)

# Save output CSV
output_path = os.path.join(repo_root, "Sources/BHARATMAPS/data/variables/RoadLengths/RoadLengths.csv")
os.makedirs(os.path.dirname(output_path), exist_ok=True)
road_lengths_up.to_csv(output_path, index=False)

print(f"✅ Total road lengths per subdistrict saved to: {output_path}")
