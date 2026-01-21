import pandas as pd
import geopandas as gpd
import os

repo_root = "/Users/stephensmathew/cdl_rep/flood-data-ecosystem-UP"

# Load data 
health_centres_gdf = gpd.read_file(
    os.path.join(repo_root, "Sources/BHARATMAPS/data/Raw Data/up_health.geojson")
)
up_sub_gdf = gpd.read_file(
    os.path.join(repo_root, "Maps/up_ids-drr_shapefiles/UP_subdistrict_final_4326.geojson")
)

# Reproject health centres to match subdistrict CRS
health_centres_gdf = health_centres_gdf.to_crs(up_sub_gdf.crs)

# Spatial join
health_in_up = gpd.sjoin(health_centres_gdf, up_sub_gdf, how="left", predicate="within")

# Count health centres per subdistrict
health_centres_count = (
    health_in_up.groupby("object_id")
    .size()
    .reset_index(name="health_centres_count")
)

# Save output
output_path = os.path.join(repo_root, "Sources/BHARATMAPS/data/variables/HealthCenters/health_count.csv")
os.makedirs(os.path.dirname(output_path), exist_ok=True)
health_centres_count.to_csv(output_path, index=False)

print("✅ Health count per subdistrict saved to:", output_path)
