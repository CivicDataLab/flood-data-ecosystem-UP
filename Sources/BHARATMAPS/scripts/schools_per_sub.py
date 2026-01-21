import geopandas as gpd
import pandas as pd
import os 


repo_root = "/Users/stephensmathew/cdl_rep/flood-data-ecosystem-UP"

# Load schools data
schools_gdf = gpd.read_file(
    os.path.join(repo_root, "Sources/BHARATMAPS/data/Raw Data/schools_up.geojson")
)

# Load UP subdistrict shapefile
up_sub_gdf = gpd.read_file(
    os.path.join(repo_root, "Maps/up_ids-drr_shapefiles/UP_subdistrict_final_4326.geojson")
)

schools_gdf = schools_gdf.to_crs(up_sub_gdf.crs)


schools_in_up = gpd.sjoin(up_sub_gdf, schools_gdf, how="left", predicate="contains")

schools_count = schools_in_up.groupby("object_id").size().reset_index(name="schools_count")

# Save output CSV
output_path = os.path.join(repo_root, "Sources/BHARATMAPS/data/variables/schools.csv")
schools_count.to_csv(output_path, index=False)

print("✅ Schools count per subdistrict saved to:", output_path)
