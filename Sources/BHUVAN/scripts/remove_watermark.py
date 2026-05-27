import glob
import os

import rasterio
from rasterio.crs import CRS

path = os.getcwd() + "/Sources/BHUVAN"
print("Base path: ", path)

# Ensure output directory exists
os.makedirs(path + "/data/tiffs/removed_watermarks", exist_ok=True)

files = glob.glob(path + "/data/tiffs/*.tif")
print("Files with watermark: ", len(files))

wm_removed_files = glob.glob(path + "/data/tiffs/removed_watermarks/*.tif")
print("Files without watermark: ", len(wm_removed_files))

dates_watermark_removed = []
for file in wm_removed_files:
    dates_watermark_removed.append(file.split(r"/")[-1].split("_w")[0])

for file in files:
    date_string = file.split(r"/")[-1][:-4]
    if date_string in dates_watermark_removed:
        print(f"Skipping {date_string}, already processed.")
        continue

    print(f"Processing: {date_string}")

    with rasterio.open(file) as raster:
        image1_ar = raster.read()

        # If Band 4 is 255 it is definitely an inundated pixel
        image1_ar[3, :, :][(image1_ar[3, :, :] < 255.0)] = 0
        image1_ar[3, :, :][(image1_ar[3, :, :] == 255.0)] = 1

        meta = raster.meta.copy()
        meta["compress"] = "deflate"
        meta["count"] = 1       # Only one band
        meta["dtype"] = "uint8"
        meta["crs"] = CRS.from_epsg(4326)
        meta["transform"] = raster.transform

    output_path = path + f"/data/tiffs/removed_watermarks/{date_string}_watermarkremoved.tif"

    with rasterio.open(output_path, "w", **meta) as dst:
        dst.write(image1_ar[3, :, :], 1)

    print(f"Saved: {output_path}")

print("Done. All files processed.")