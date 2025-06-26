import os
import sys
from datetime import datetime
os.environ["PROJ_LIB"] = r"C:\Program Files\QGIS 3.42.3\share\proj"
gdal_calc = r'"C:\Program Files\QGIS 3.42.3\apps\gdal\share\bash-completion\completions\gdal_calc.py"'

os.environ["PROJ_LIB"] = r"C:\Program Files\QGIS 3.42.3\share\proj"
os.environ["GDAL_DATA"] = r"C:\Program Files\QGIS 3.42.3\share\gdal"

from osgeo.gdal import deprecation_warn
import geopandas as gpd
import imdlib as imd
import numpy as np
import pandas as pd
import rasterio
import rasterstats
from rasterio.crs import CRS
from rasterio.transform import Affine
import rioxarray

path = os.getcwd()

CURRENT_FOLDER = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.abspath(CURRENT_FOLDER + "/../" + "data")
TIFF_DATA_FOLDER = os.path.join(DATA_FOLDER, "rain", "tiff")
CSV_DATA_FOLDER = os.path.join(DATA_FOLDER, "rain", "csv")

ADMIN_BDRY_GDF = gpd.read_file(r"D:\CDL\flood-data-ecosystem-UP\Maps\up_ids-drr_shapefiles\UP_Subdistrict_final_simplified.geojson")


def download_data(year: int, start_date: str, end_date: str):
    """
    Download year wise data in the DATA_FOLDER
    The year wise data has datapoint for all days of all months
    """
    current_year = datetime.now().year
    if year == current_year:
        imd.get_real_data(
            var_type="rain",
            start_dy=start_date,
            end_dy=end_date,
            file_dir=DATA_FOLDER,
        )
    else:
        imd.get_data(
            var_type="rain",
            start_yr=year,
            end_yr=year,
            fn_format="yearwise",
            file_dir=DATA_FOLDER,
        )
    return None


def transform_resample_monthly_tif_filenames(tif_filename: str):
    """
    Transform and resample monthly tif files
    """

    # Define the transformation parameters
    pixel_width = 0.25
    rot_x = 0.0
    rot_y = 0.0
    pixel_height = -0.25
    x_coordinate = 66.375
    y_coordinate = 38.625

    new_transform = Affine(pixel_width, rot_x, x_coordinate, rot_y, pixel_height, y_coordinate)

    with rasterio.open(tif_filename, "r+") as raster:
        raster.crs = CRS.from_epsg(4326)
        raster_array = raster.read(1)
        nan_mask = np.isnan(raster_array)
        raster_array[nan_mask] = -999
        raster.nodata = -999
        raster.transform = new_transform
        meta = raster.meta

    meta["transform"] = new_transform
    reversed_data = np.flipud(raster_array)

    flipped_file = tif_filename.replace(".tif", "_flipped.tif")
    with rasterio.open(flipped_file, "w", **meta) as dst:
        dst.write(reversed_data, 1)

    # Paths (no extra quotes here)
    gdalwarp_path = r"C:\Program Files\QGIS 3.42.3\bin\gdalwarp.exe"
    gdalcalc_path = r"C:\Program Files\QGIS 3.42.3\apps\Python312\Scripts\gdal_calc.py"
    python_path = r"C:\Program Files\QGIS 3.42.3\bin\python-qgis.bat"

    resampled_file = tif_filename.replace(".tif", "_resampled.tif")
    resampled2_file = tif_filename.replace(".tif", "_resampled2.tif")

    # Use quotes properly around file paths
    warp_cmd = f'"{gdalwarp_path}" -tr 0.01 -0.01 -r sum "{flipped_file}" "{resampled_file}" -co COMPRESS=DEFLATE'
    os.system(warp_cmd)

    # Normalize using gdal_calc
    calc_cmd = f'"{python_path}" "{gdalcalc_path}" -A "{resampled_file}" --outfile="{resampled2_file}" --calc="A/625" --NoDataValue=-999 --creation-option=COMPRESS=DEFLATE'
    os.system(calc_cmd)

def parse_and_format_data(year: int, start_date: str, end_date: str):
    """
    Parses the year wise data in the DATA_FOLDER and formats to required type
    """
    current_year = datetime.now().year
    if year == current_year:
        data = imd.open_real_data(
            var_type="rain",
            start_dy=start_date,
            end_dy=end_date,
            file_dir=DATA_FOLDER,
        )
    else:
        data = imd.open_data(
            var_type="rain",
            start_yr=year,
            end_yr=year,
            fn_format="yearwise",
            file_dir=DATA_FOLDER,
        )

    dataset = data.get_xarray()

    # Remove NaN values
    dataset = dataset.where(dataset["rain"] != -999.0)
    # Group the dataset by month
    dataset = dataset.groupby("time.month")

    # Make sure TIFF_DATA_FOLDER exists
    os.makedirs(TIFF_DATA_FOLDER, exist_ok=True)
    
    # For each month in the dataset, save the total rain in tif format
    for el in dataset:
        month = el[1]["time.month"].to_dict()["data"][0]
        if month < 10:
            month_wise_tif_filename = TIFF_DATA_FOLDER + "/{}_0{}.tif".format(
                year, month
            )
        else:
            month_wise_tif_filename = TIFF_DATA_FOLDER + "/{}_{}.tif".format(
                year, month
            )

        el[1]["rain"].sum("time").rio.to_raster(month_wise_tif_filename)

        transform_resample_monthly_tif_filenames(month_wise_tif_filename)

    # Save yearwise file as geotiff, this is used in getting crs
    data.to_geotiff("{}.tif".format(year), TIFF_DATA_FOLDER)

    return None


def retrieve_assam_revenue_circle_data(year: int):
    """
    Retrives assam revenue circle data from the year wise .tif file
    """
    for month in [
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
    ]:
        month_and_year_filename = "{}_{}".format(str(year), str(month))
        try:
            raster = rasterio.open(
                os.path.join(
                    TIFF_DATA_FOLDER,
                    "{}_resampled2.tif".format(month_and_year_filename),
                )
            )
            print(f"Processing for {month_and_year_filename}")
        except rasterio.errors.RasterioIOError:
            print(f"Skipping for {month_and_year_filename} - File Not Found!!")
            continue

        raster_array = raster.read(1)

        
        print("Raster CRS:", raster.crs)
        print("Vector CRS before conversion:", ADMIN_BDRY_GDF.crs)

        if raster.crs is None:
            raise ValueError("Raster CRS is not defined!")

        if ADMIN_BDRY_GDF.crs is None:
            raise ValueError("Vector CRS is not defined!")

        vector_in_raster_crs = ADMIN_BDRY_GDF.to_crs(raster.crs)

        mean_dicts = rasterstats.zonal_stats(
            vector_in_raster_crs,
            raster_array,
            affine=raster.transform,
            stats=["count", "mean", "sum", "max"],
            nodata=raster.nodata,
            geojson_out=True,
        )

        

        dfs = []

        for revenue_circle in mean_dicts:
            dfs.append(pd.DataFrame([revenue_circle["properties"]]))

        zonal_stats_df = pd.concat(dfs).reset_index(drop=True)

        os.makedirs(CSV_DATA_FOLDER, exist_ok=True)

        zonal_stats_df.to_csv(
            CSV_DATA_FOLDER + "/{}.csv".format(month_and_year_filename), index=False
        )

    return None


if __name__ == "__main__":

    # Takes year as an input from the cli
    year = str(sys.argv[1])
    year = int(year)

    # IF the year is current year, specify start and end date
    start_date = "2020-01-01"
    end_date = "2020-06-30"

    download_data(year, start_date=start_date, end_date=end_date)
    parse_and_format_data(year, start_date=start_date, end_date=end_date)
    retrieve_assam_revenue_circle_data(year)
