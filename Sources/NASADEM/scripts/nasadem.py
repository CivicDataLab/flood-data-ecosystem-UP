import ee
import geemap
import geopandas as gpd
import os
import time

# ===== CONFIG =====
SERVICE_ACCOUNT = 'nasadem-service-acct@nasadem-project-idsdrr.iam.gserviceaccount.com'
KEY_PATH = '/Users/stephensmathew/Downloads/nasadem-project-idsdrr-bf0ff5b49ce8.json'
PROJECT = 'nasadem-project-idsdrr'
GCS_BUCKET = 'nasadem-up-exports'    # ensure this exists and SA has Storage Object Admin
GCS_PREFIX = 'UP_NASADEM'            # folder-like prefix inside the bucket
GEOJSON_PATH = os.path.join(os.getcwd(), "Maps/up_ids-drr_shapefiles/UP_subdistrict_final_4326.geojson")
SCALE = 30
MAXPIX = 1e13

# 1. Initialize EE 
credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_PATH)
ee.Initialize(credentials, project=PROJECT)
print("✅ Earth Engine initialized for project:", PROJECT)

# 2. Load UP shapefile 
up_sub_gdf = gpd.read_file(GEOJSON_PATH)
if up_sub_gdf.crs is None or up_sub_gdf.crs.to_epsg() != 4326:
    up_sub_gdf = up_sub_gdf.to_crs(4326)
# dissolve to single geometry and simplify a bit (reduces export request size)
up_sub_gdf = up_sub_gdf.dissolve().reset_index(drop=True)
print("✅ Loaded and dissolved UP shapefile")

#  3. Convert to EE geometry 
up_fc = geemap.geopandas_to_ee(up_sub_gdf)
geom_union = up_fc.geometry()                     
geom_simple = geom_union.simplify(maxError=100)   
region_rect = geom_union.bounds()                 # use bounds as region to keep payload small
region_coords = region_rect.getInfo()['coordinates']
print("✅ Converted to EE geometry (union + simplified)")

# ===== 4. Prepare images =====
nasadem = ee.Image('NASA/NASADEM_HGT/001').select('elevation')
elevation = nasadem.clip(geom_union)  # clip with full geometry so mask is correct
slope = ee.Terrain.slope(nasadem).clip(geom_union)
print("✅ NASADEM elevation and slope ready")

# ===== 5. Export to Cloud Storage =====
try:
    dem_task = ee.batch.Export.image.toCloudStorage(
        image=elevation,
        description='UP_NASADEM_DEM_30',
        bucket=GCS_BUCKET,
        fileNamePrefix=f'{GCS_PREFIX}/UP_NASADEM_DEM_30',
        region=region_coords,
        scale=SCALE,
        maxPixels=MAXPIX,
        fileFormat='GeoTIFF'
    )
    dem_task.start()
    print(f"📤 DEM export started. Task ID: {dem_task.id}")
except Exception as e:
    print("❌ Failed to start DEM export:", e)

try:
    slope_task = ee.batch.Export.image.toCloudStorage(
        image=slope,
        description='UP_NASADEM_SLOPE_30',
        bucket=GCS_BUCKET,
        fileNamePrefix=f'{GCS_PREFIX}/UP_NASADEM_SLOPE_30',
        region=region_coords,
        scale=SCALE,
        maxPixels=MAXPIX,
        fileFormat='GeoTIFF'
    )
    slope_task.start()
    print(f"📤 Slope export started. Task ID: {slope_task.id}")
except Exception as e:
    print("❌ Failed to start slope export:", e)

# ===== 6. Small helper: how to monitor tasks =====
print("\n🕓 Monitor tasks with:")
print("""
import ee
ee.Initialize(ee.ServiceAccountCredentials('{}', '{}'), project='{}')
for t in ee.data.getTaskList():
    print(t['id'], t['metadata'].get('description'), t['metadata'].get('state'))
""".format(SERVICE_ACCOUNT, KEY_PATH, PROJECT))

print("\n✅ Exports submitted. When tasks show COMPLETED, files will be in:")
print(f"  gs://{GCS_BUCKET}/{GCS_PREFIX}/")
