import os
import subprocess
import time
import timeit
import socket

import numpy as np
import rasterio
from osgeo import gdal

gdal.DontUseExceptions()

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
    "2026_31_08_18", "2026_30_08_18", "2026_29_08_18", "2026_29_08_10",
    "2026_29_08_06", "2026_27_08_06", "2026_25_08_18", "2026_23_08_10",
    "2026_24_08_06", "2026_22_08_18", "2026_22_08_06", "2026_21_08_18",
    "2026_21_08_06", "2026_20_08_18", "2026_20_08_06", "2026_18_08_06",
    "2026_17_08_06", "2026_14_08_18", "2026_15_08_06", "2026_11_08_18",
    "2026_11_08_06", "2026_10_08_06", "2026_05_08_06",
]


def host_reachable(hostname, retries=3, delay=5):
    for attempt in range(retries):
        try:
            socket.gethostbyname(hostname)
            return True
        except socket.gaierror:
            print(f"DNS lookup failed for {hostname}, retry {attempt + 1}/{retries}...")
            time.sleep(delay)
    return False


def fetch_and_warp(dates, attempt_label=""):
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
        print(f"{attempt_label}WMS fetch failed for {dates}")
        print("  stderr:", result.stderr)
        print("  xml:", xml_content[:300])
        return False

    xml_content = xml_content.replace("<BlockSizeX>1024</BlockSizeX>", "<BlockSizeX>512</BlockSizeX>")
    xml_content = xml_content.replace("<BlockSizeY>1024</BlockSizeY>", "<BlockSizeY>512</BlockSizeY>")
    with open(input_xml_path, "w") as f:
        f.write(xml_content)

    print(f"{attempt_label}Warping {dates} ...")
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

    print(f"  Time taken: {timeit.default_timer() - starttime:.1f}s")

    # Post-warp sanity check: gdal.Warp doesn't raise on failed/blank tiles
    with rasterio.open(output_tiff_path) as chk:
        band4 = chk.read(4)
        nonzero = np.count_nonzero(band4)
        if nonzero == 0:
            print(f"  WARNING: {dates}.tif came back completely empty")
            return False
        print(f"  OK: {dates}.tif has {nonzero} nonzero alpha pixels")
    return True


if not host_reachable(url_as.split("/")[2]):
    print("Host unreachable — check your network/VPN before proceeding.")
    raise SystemExit(1)

failed_dates = []

for dates in date_strings:
    success = fetch_and_warp(dates)
    if not success:
        print(f"Retrying {dates} once after a short pause...")
        time.sleep(10)
        success = fetch_and_warp(dates, attempt_label="[retry] ")
    if not success:
        failed_dates.append(dates)

    # Small pause between requests so we don't hammer a slow/flaky govt server
    time.sleep(2)

print("\n=== Run complete ===")
if failed_dates:
    print(f"{len(failed_dates)} date(s) still failed after retry:")
    for d in failed_dates:
        print(" -", d)
else:
    print("All dates fetched successfully.")