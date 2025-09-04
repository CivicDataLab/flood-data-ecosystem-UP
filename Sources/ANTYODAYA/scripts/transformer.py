import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# File paths

villages_fp = "/Users/stephensmathew/cdl_rep/flood-data-ecosystem-UP/Maps/up_ids-drr_shapefiles/UP_Villages_Boundary_Simplified.geojson"
subdistricts_fp = "/Users/stephensmathew/cdl_rep/flood-data-ecosystem-UP/Maps/up_ids-drr_shapefiles/UP_Subdistrict_final_modified.geojson"
antyodaya_csv_fp = "/Users/stephensmathew/cdl_rep/flood-data-ecosystem-UP/Sources/ANTYODAYA/data/antyodaya_raw_data.csv"
output_csv_fp = "/Users/stephensmathew/cdl_rep/flood-data-ecosystem-UP/Sources/ANTYODAYA/data/UP_ANTYODAYA.csv"


# Load Antyodaya CSV and convert to GeoDataFrame

mission_antodaya_df = pd.read_csv(antyodaya_csv_fp)

gdf_points = gpd.GeoDataFrame(
    mission_antodaya_df,
    geometry=[Point(xy) for xy in zip(mission_antodaya_df.village_longitude,
                                      mission_antodaya_df.village_latitude)],
    crs="EPSG:4326"
)


# Load subdistrict polygons and reproject

gdf_polygons = gpd.read_file(subdistricts_fp).to_crs("EPSG:4326")


# Spatial join: points within polygons

results = gpd.sjoin(gdf_points, gdf_polygons, how="left", predicate="within")

# -------------------------------
# Clean subdistrict code and name
# -------------------------------
# Rename code column and strip leading zeros
gdf_polygons = gdf_polygons.rename(columns={'sdtcode11': 'sub_district_code'})
gdf_polygons['sub_district_code'] = gdf_polygons['sub_district_code'].astype(str).str.lstrip("0")

# Format subdistrict names
def format_entry(entry):
    if pd.isnull(entry):
        return entry
    entry = entry.lower().replace(' ', '_').replace('.', '-')
    return entry

results['subdistrict_name'] = results['subdistrict_name'].apply(format_entry)

# Merge cleaned subdistrict codes into results
results = results.merge(
    gdf_polygons[['sub_district_code', 'subdistrict_name']],
    on='subdistrict_name',
    how='left'
)

# -------------------------------
# Select final columns and save CSV
# -------------------------------
final_columns = [
    'gp_code',
    'village_code',
    'sub_district_code',
    'subdistrict_name',
    'total_hhd',
    'availablility_hours_of_domestic_electricity',
    'availability_of_telephone_services',
    'total_hhd_having_piped_water_connection',
    'total_hhd_not_having_sanitary_latrines'
]

results[final_columns].to_csv(output_csv_fp, index=False)
print(f"CSV saved to: {output_csv_fp}")
