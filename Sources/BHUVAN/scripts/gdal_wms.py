import os
import subprocess
import timeit

from osgeo import gdal

gdal.DontUseExceptions()

path = os.getcwd() + "/Sources/BHUVAN/"
os.makedirs(path + "data/tiffs/", exist_ok=True)

layer_code = "up"  # FOR UP 
layer = f"flood%3A{layer_code}"
bbox_up = "77.0,23.8,84.7,30.5"
url_as = "https://bhuvan-gp1.nrsc.gov.in/bhuvan/wms"

date_strings = [
    "2025_05_09_06",   # 05/09/2025-06Hr
    "2025_06_09_06",   # 06/09/2025-06Hr
    "2025_13_09_06",   # 13/09/2025-06Hr
    "2025_15_09_06",   # 15/09/2025-06Hr
    "2025_18_09_18",   # 18/09/2025-18Hr
    "2025_10_09_18",   # 10/09/2025-18Hr
    "2025_11_09_06",   # 11/09/2025-06Hr
    "2025_17_09_18",   # 17/09/2025-18Hr
    "2025_11_09_10",   # 11/09/2025-10Hr
    "2025_30_06_18",   # 30/06/2025-18Hr
    "2025_18_07_11",   # 18/07/2025-11Hr
    "2025_21_07_18",   # 21/07/2025-18Hr
    "2025_21_07_10",   # 21/07/2025-10Hr
    "2025_31_07_06",   # 31/07/2025-06Hr
    "2025_02_08_06",   # 02/08/2025-06Hr
    "2025_03_08_06",   # 03/08/2025-06Hr
    "2025_03_08_18",   # 03/08/2025-18Hr
    "2025_04_08_06",   # 04/08/2025-06Hr
    "2025_05_08_18",   # 05/08/2025-18Hr
    "2025_07_08_18",   # 07/08/2025-18Hr
    "2025_08_08_06",   # 08/08/2025-06Hr
    "2025_07_09_10",   # 07/09/2025-10Hr
    "2025_10_08_06",   # 10/08/2025-06Hr
    "2025_10_08_18",   # 10/08/2025-18Hr
    "2025_10_08_10",   # 10/08/2025-10Hr
    "2025_12_08_06",   # 12/08/2025-06Hr
    "2025_13_08_06",   # 13/08/2025-06Hr
    "2025_14_08_18",   # 14/08/2025-18Hr
    "2025_15_08_10",   # 15/08/2025-10Hr
    "2025_15_08_06",   # 15/08/2025-06Hr
    "2025_17_08_18",   # 17/08/2025-18Hr
    "2025_18_08_06",   # 18/08/2025-06Hr
    "2025_19_08_06",   # 19/08/2025-06Hr
    "2025_19_08_18",   # 19/08/2025-18Hr
    "2025_20_08_06",   # 20/08/2025-06Hr
    "2025_20_08",      # 20/08/2025 (no time)
    "2025_27_08_06",   # 27/08/2025-06Hr
    "2025_28_08_06",   # 28/08/2025-06Hr
    "2025_29_08_18",   # 29/08/2025-18Hr
    "2025_30_08_06",   # 30/08/2025-06Hr
    "2025_31_08_18",   # 31/08/2025-18Hr  
    "2025_01_09_06",   # 01/09/2025-06Hr
    "2025_01_09_18",   # 01/09/2025-18Hr
    "2025_01_09_10",   # 01/09/2025-10Hr
    "2025_03_09_06",   # 03/09/2025-06Hr
    "2025_03_09_18",   # 03/09/2025-18Hr
    "2025_05_09_18",   # 05/09/2025-18Hr
    "2025_08_09_06",   # 08/09/2025-06Hr
    "2025_12_09_18",   # 12/09/2025-18Hr
    "2025_20_09_06",   # 20/09/2025-06Hr
    "2025_20_09_10",   # 20/09/2025-10Hr
    "2025_22_09_06",   # 22/09/2025-06Hr
    "2025_25_09_10",   # 25/09/2025-10Hr
    "2025_26_09_10",   # 26/09/2025-10Hr
    "2025_27_09_06",   # 27/09/2025-06Hr
    "2025_27_09_18",   # 27/09/2025-18Hr
    "2025_06_10_18",   # 06/10/2025-18Hr
    "2025_07_10_06",   # 07/10/2025-06Hr
    "2025_09_10_06"    # 09/10/2025-06Hr
]

for dates in date_strings:

    # Define your input and output paths
    input_xml_path = path + "/data/inundation.xml"
    output_tiff_path = path + f"/data/tiffs/{dates}.tif"
 
    # Download the WMS(Web Map Sevice) layer and save as XML.
    command = [
        "gdal_translate",
        "-of",
        "WMS",
        f"WMS:{url_as}?&LAYERS={layer}_{dates}&TRANSPARENT=TRUE&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&STYLES=&FORMAT=image%2Fpng&SRS=EPSG%3A4326&BBOX={bbox_up}",
        f"{path}/data/inundation.xml",
    ]
    subprocess.run(command)

    # Specify the target resolution in the X and Y directions (50 meters)
    target_resolution_x = 0.00044915  # 0.0008983  # 0.0001716660336923202072
    target_resolution_y = -0.00044915  # -0.0008983  # -0.0001716684356881450775

    # Perform the warp operation using gdal.Warp()
    print("Warping Started")
    starttime = timeit.default_timer()

    gdal.Warp(
        output_tiff_path,
        input_xml_path,
        format="GTiff",
        xRes=target_resolution_x,
        yRes=target_resolution_y,
        creationOptions=["COMPRESS=DEFLATE", "TILED=YES"],
        callback=gdal.TermProgress,
    )

    print("Time took to Warp: ", timeit.default_timer() - starttime)
    print(f"Warping completed. Output saved to: {output_tiff_path}")
