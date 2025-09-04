import os
import geopandas as gpd
import pandas as pd
import regex as re
import numpy as np

def main():
    # Set repo_root to the top-level directory
    repo_root = "/Users/stephensmathew/cdl_rep/flood-data-ecosystem-UP"
    print("Repo root:", repo_root)

    # Correct input paths
    up_sub_file = os.path.join(repo_root, "Maps", "up_ids-drr_shapefiles", "UP_Subdistrict_final_modified.geojson")
    up_vil_path = os.path.join(repo_root, "Maps", "up_ids-drr_shapefiles", "UP_Villages_Boundary_Simplified.zip")

    # Check if input files exist
    if not os.path.exists(up_sub_file):
        raise FileNotFoundError(f"Subdistrict file not found: {up_sub_file}")
    if not os.path.exists(up_vil_path):
        raise FileNotFoundError(f"Village file not found: {up_vil_path}")

    # Load subdistrict boundaries
    print("Loading subdistrict boundaries...")
    od_block = gpd.read_file(up_sub_file)
    od_block.set_crs(epsg=32644, inplace=True, allow_override=True)
    od_block = od_block.to_crs(epsg=4326)

    # Load village boundaries
    print("Loading village boundaries...")
    up_vil_unfiltered = gpd.read_file(up_vil_path)
    up_vil = up_vil_unfiltered.replace(r'^\s*$', np.nan, regex=True)
    up_vil = up_vil.dropna(subset=['vilnam_soi', 'vilname11', 'vilcode11'])
    up_vil = up_vil.loc[up_vil["stname"] == "UTTAR PRADESH"]
    up_vil["vilnam_soi"] = up_vil["vilnam_soi"].str.upper()

    # Remove forests/hills
    forest_regex = r'FOREST|RF|RESERVED FOREST| RF|HILL|R F'
    up_vil = up_vil[~up_vil["vilnam_soi"].str.contains(forest_regex, na=False)]

    # Format codes
    up_vil["dtcode11"] = up_vil["dtcode11"].astype(str).str.zfill(2)
    up_vil["block_lgd"] = up_vil["block_lgd"].astype(float).astype(int).astype(str).str.zfill(5)
    up_vil['object_id'] = up_vil.apply(lambda row: f"21-{row['dtcode11']}-{row['block_lgd']}", axis=1)

    # Drop unnecessary columns
    up_vil.drop(["objectid", "remark", "ac_no"], axis=1, inplace=True, errors='ignore')

    # Save cleaned village geojson
    up_vil_geojson_path = os.path.join(repo_root, "Maps", "up_ids-drr_shapefiles", "UP_Villages_Boundary_Simplified.geojson")
    up_vil.to_file(up_vil_geojson_path, driver="GeoJSON")
    print(f"Saved cleaned village file: {up_vil_geojson_path}")

    # Filter urban areas
    up_urban = gpd.read_file(up_vil_geojson_path)
    up_urban = up_urban.dropna(subset=['vilnam_soi'])
    up_urban = up_urban.loc[up_urban["stcode11"] == "09"]

    urban_filter = [
        'kanpur','lucknow','ghaziabad','agra','varanasi','meerut','prayagraj','bareilly',
        'aligarh','gorakhpur','ayodhya','jhansi','muzaffarnagar','mathura','rampur',
        'shahjahanpur','farrukhabad','mirzapur','bulandshahr','hardoi','orai','sitapur',
        'modinagar','lakhimpur','hathras','banda','pilibhit','khurja','gonda','mainpuri',
        'etah','ghazipur','sultanpur','azamgarh','ballia',
        '(NPP)','(M Corp.)','(NP)','(OG)','(CB)','(CT)'
    ]

    filtered_gdf = up_urban[up_urban['vilname11'].str.contains('|'.join(urban_filter), na=False, case=False)]

    # Merge with village codes
    merged = filtered_gdf.merge(
        up_vil[['vilcode11']],
        on='vilcode11',
        how='left'
    )

    if 'vilcode11' in merged.columns:
        merged.drop('vilcode11', axis=1, inplace=True)

    # Convert to GeoDataFrame and save
    final_gdf = gpd.GeoDataFrame(merged, geometry='geometry')
    output_path = os.path.join(repo_root, "Maps", "up_ids-drr_shapefiles", "up_urban_final.geojson")
    final_gdf.to_file(output_path, driver="GeoJSON")
    print(f"Final GeoJSON saved to {output_path}")

if __name__ == "__main__":
    main()
