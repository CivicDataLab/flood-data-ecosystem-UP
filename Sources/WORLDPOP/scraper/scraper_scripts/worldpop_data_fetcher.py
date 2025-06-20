import os
import json
import time
import requests
import urllib.parse
import csv
from pathlib import Path
from shapely.geometry import shape, mapping
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

year="2020"

class WorldPopDataFetcher:
    def __init__(self, base_url="https://api.worldpop.org/v1"):
        self.base_url = base_url
        self.output_dir = Path(r"D:\CDL\flood-data-ecosystem-UP\Sources\WORLDPOP\data\agesexstructure") / str(year)
        self.output_dir.mkdir(exist_ok=True)

    def simplify_geometry(self, geojson, tolerance=0.1):
        feature = geojson['features'][0]
        geom = shape(feature['geometry'])
        simplified = geom.simplify(tolerance)
        feature['geometry'] = mapping(simplified)
        return geojson

    def truncate_coordinates(self, geojson, precision=2):
        def _truncate(x): return round(float(x), precision)

        feature = geojson['features'][0]
        coords = feature['geometry']['coordinates']

        if feature['geometry']['type'] == 'Polygon':
            feature['geometry']['coordinates'] = [[[_truncate(x) for x in point]
                                                   for point in ring]
                                                  for ring in coords]
        elif feature['geometry']['type'] == 'MultiPolygon':
            feature['geometry']['coordinates'] = [[[[_truncate(x) for x in point]
                                                  for point in ring]
                                                   for ring in poly]
                                                  for poly in coords]
        return geojson

    def fetch_worldpop_data(self, geojson_path, year=year):
        try:
            with open(geojson_path) as f:
                geojson = json.load(f)

            district = Path(geojson_path).stem

            # Apply both simplification and truncation
            geojson = self.simplify_geometry(geojson)
            # geojson = self.truncate_coordinates(geojson)

            # pop_data = self._make_api_call(geojson, "wpgppop", year, district)
            # # print(pop_data)
            # if pop_data:
            #     self._save_population_data(pop_data, district)

            pyramid_data = self._make_api_call(
                geojson, "wpgpas", year, district)

            if pyramid_data:
                logger.info(
                    f"Pyramid data for district {district} is {pyramid_data}")
                self._save_pyramid_data(pyramid_data, district, year)

        except Exception as e:
            logger.error(f"Error processing {district}: {str(e)}")
            return False
        return True

    def _make_api_call(self, geojson, dataset, year, district):
        try:
            geojson = json.dumps(geojson)
            url = f"{self.base_url}/services/stats"
            params = {
                "dataset": dataset,
                "year": year,
                "geojson": geojson,
                "runasync": "false"
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            logger.info(f"The response is {response.json()}")
            task_id = response.json()["taskid"]

            attempt = 0
            while attempt < 2:
                time.sleep(2)
                status_url = f"{self.base_url}/tasks/{task_id}"
                status_response = requests.get(status_url)
                status_response.raise_for_status()

                result = status_response.json()
                if result.get("status") == "finished":
                    logger.info(f"Task info is {result}")
                    return result
                elif result.get("status") == "failed":
                    return None

                attempt += 1
            return None

        except requests.RequestException as e:
            if "413" in str(e):
                logger.error(f"Payload still too large for {district}")
            return None

    def _save_population_data(self, data, district):
        output_file = self.output_dir / f"{district}_population.csv"
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['district', 'total_population'])
            writer.writerow([district, data['data']['total_population']])

    def _save_pyramid_data(self, data, year, district):
        if not data or 'data' not in data or 'agesexpyramid' not in data['data']:
            logger.error(f"No valid pyramid data found for {district}: {data}")
            return

        output_file = self.output_dir / f"{district}_{year}.csv"
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(
                f, fieldnames=['class', 'age', 'male', 'female'])
            writer.writeheader()
            for row in data['data']['agesexpyramid']:
                writer.writerow(row)



def main():
    fetcher = WorldPopDataFetcher()
    geojson_dir = Path(
        r"D:\CDL\flood-data-ecosystem-UP\Sources\WORLDPOP\data copy\shapefiles\district_geojson")

    for geojson_file in geojson_dir.glob("*.geojson"):
        logger.info(f"Processing {geojson_file.name}")
        fetcher.fetch_worldpop_data(str(geojson_file))


if __name__ == "__main__":
    main()
