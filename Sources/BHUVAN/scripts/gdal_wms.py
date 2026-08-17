import os
import subprocess
import timeit

from osgeo import gdal

gdal.DontUseExceptions()

# Make GDAL retry flaky/truncated downloads instead of silently giving up per-tile
os.environ["GDAL_HTTP_TIMEOUT"] = "120"
os.environ["GDAL_HTTP_CONNECTTIMEOUT"] = "30"
os.environ["GDAL_HTTP_MAX_RETRY"] = "5"
os.environ["GDAL_HTTP_RETRY_DELAY"] = "5"
gdal.SetConfigOption("GDAL_HTTP_TIMEOUT", "120")
gdal.SetConfigOption("GDAL_HTTP_MAX_RETRY", "5")
gdal.SetConfigOption("GDAL_HTTP_RETRY_DELAY", "5")

path = os.getcwd() + "/Sources/BHUVAN/"
os.makedirs(path + "data/tiffs/", exist_ok=True)

layer_code = "up"
layer = f"flood%3A{layer_code}"
bbox_up = "77.03,23.87,84.64,30.41"

target_resolution_x = 0.00044915
target_resolution_y = -0.00044915

bbox_w = 84.64 - 77.03
bbox_h = 30.41 - 23.87
width_px = round(bbox_w / target_resolution_x)
height_px = round(bbox_h / abs(target_resolution_y))

url_as = "https://bhuvan-gp1.nrsc.gov.in/bhuvan/wms"

date_strings = [
    "2026_21_07_18"
]

for dates in date_strings:
    input_xml_path = path + "/data/inundation.xml"
    output_tiff_path = path + f"/data/tiffs/{dates}.tif"

    command = [
        "gdal_translate", "-of", "WMS",
        f"WMS:{url_as}?&LAYERS={layer}_{dates}&TRANSPARENT=TRUE&SERVICE=WMS"
        f"&VERSION=1.1.1&REQUEST=GetMap&STYLES=&FORMAT=image%2Fpng&SRS=EPSG%3A4326"
        f"&BBOX={bbox_up}&WIDTH={width_px}&HEIGHT={height_px}",
        f"{path}/data/inundation.xml",
    ]

    result = subprocess.run(command, capture_output=True, text=True)

    xml_content = open(input_xml_path).read()
    if result.returncode != 0 or "ServiceException" in xml_content:
        print(f"WMS fetch failed for {dates}")
        print("stderr:", result.stderr)
        print("xml:", xml_content[:500])
        continue

    # Shrink the block size so each individual HTTP tile request is smaller
    # and less likely to time out / get truncated on a slow server.
    xml_content = xml_content.replace("<BlockSizeX>1024</BlockSizeX>", "<BlockSizeX>512</BlockSizeX>")
    xml_content = xml_content.replace("<BlockSizeY>1024</BlockSizeY>", "<BlockSizeY>512</BlockSizeY>")
    with open(input_xml_path, "w") as f:
        f.write(xml_content)

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