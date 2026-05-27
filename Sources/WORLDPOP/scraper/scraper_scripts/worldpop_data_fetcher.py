"""
WorldPopDataFetcher
- Uses WorldPop SDI advanced API (https://api.worldpop.org/v1/services)
- Supports datasets: wpgppop (total pop) and wpgpas (age-sex pyramid)
- Handles async tasks (/tasks/{taskid}) with polling + exponential backoff
- Geometry simplification + coordinate truncation to avoid payload-too-large (413)
"""

import os
import json
import time
import math
import logging
import requests
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_YEAR = "2020"


class WorldPopDataFetcher:
    def __init__(
        self,
        base_url="https://api.worldpop.org/v1",   \
        year=DEFAULT_YEAR,
        output_dir=None,
        api_key=None,
        simplify_tolerance=0.01,
        truncate_precision=None,
        async_threshold=1500,
    ):
        self.base_url = base_url.rstrip("/")
        self.year = str(year)
        self.api_key = api_key  # optional
        self.simplify_tolerance = simplify_tolerance
        self.truncate_precision = truncate_precision  # None means don't truncate
        self.async_threshold = async_threshold  # bytes length threshold to prefer async

        # If output_dir is not provided, create/use a year-based directory
      
        # If the folder already exists, this will NOT delete it; just reuse it
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using output directory: {self.output_dir}")

    # ---------- geometry helpers ----------
    def simplify_geometry(self, geojson, tolerance=None):
        """Simplify geometry (keeps FeatureCollection -> first feature)."""
        tol = tolerance if tolerance is not None else self.simplify_tolerance
        feature = geojson["features"][0]
        geom = shape(feature["geometry"])
        simplified = geom.simplify(float(tol), preserve_topology=True)
        feature["geometry"] = mapping(simplified)
        return geojson

    def truncate_coordinates(self, geojson, precision=None):
        """Round coordinates to reduce payload size."""
        if precision is None:
            precision = self.truncate_precision
        if precision is None:
            return geojson

        def _trunc(x):
            return round(float(x), precision)

        feature = geojson["features"][0]
        geom_type = feature["geometry"]["type"]
        coords = feature["geometry"]["coordinates"]

        if geom_type == "Polygon":
            feature["geometry"]["coordinates"] = [
                [[_trunc(x) for x in pt] for pt in ring] for ring in coords
            ]
        elif geom_type == "MultiPolygon":
            feature["geometry"]["coordinates"] = [
                [[[ _trunc(x) for x in pt] for pt in ring] for ring in poly] for poly in coords
            ]
        else:
            # For other geometry types, best-effort: try mapping and rounding recursively
            pass

        return geojson

    def _prepare_geojson(self, geojson_path):
        """Load + simplify + optionally truncate geometry. Returns dict and stringified JSON."""
        with open(geojson_path, "r") as fh:
            gj = json.load(fh)

        # Ensure FeatureCollection with at least one feature
        if "features" not in gj or len(gj["features"]) == 0:
            raise ValueError("GeoJSON must be a FeatureCollection with at least one feature")

        # Simplify
        gj = self.simplify_geometry(gj, tolerance=self.simplify_tolerance)

        # Optionally truncate
        if self.truncate_precision is not None:
            gj = self.truncate_coordinates(gj, precision=self.truncate_precision)

        # Final JSON string
        geojson_str = json.dumps(gj, separators=(",", ":"))
        return gj, geojson_str

    # ---------- API helpers ----------
    def _build_params(self, dataset, year, geojson_str, runasync):
        params = {
            "dataset": dataset,
            "year": str(year),
            "geojson": geojson_str,
            "runasync": "true" if runasync else "false",
        }
        if self.api_key:
            params["key"] = self.api_key
        return params

    def _poll_task(self, task_id, max_attempts=12, initial_delay=1.0, max_delay=30.0):
        """Poll /tasks/{taskid} with exponential backoff until finished/failed or attempts exhausted.
        Returns the JSON response for the finished task (contains 'data') or None.
        """
        task_url = f"{self.base_url}/tasks/{task_id}"
        attempt = 0
        delay = float(initial_delay)

        while attempt < max_attempts:
            logger.info(f"Polling task {task_id} (attempt {attempt + 1}/{max_attempts})")
            try:
                resp = requests.get(task_url, timeout=30)
                if resp.status_code == 413:
                    logger.error("Task status endpoint returned 413")
                    return None
                resp.raise_for_status()
                j = resp.json()
            except requests.RequestException as e:
                logger.warning(f"Polling request failed: {e}. Retrying after {delay:.1f}s")
                time.sleep(delay)
                attempt += 1
                delay = min(delay * 2, max_delay)
                continue

            status = j.get("status")
            if status == "finished":
                logger.info(f"Task {task_id} finished")
                return j
            if status == "failed":
                logger.error(f"Task {task_id} failed: {j.get('error_message')}")
                return None

            # still running
            logger.debug(f"Task {task_id} status: {status}. Sleeping {delay:.1f}s")
            time.sleep(delay)
            attempt += 1
            delay = min(delay * 2, max_delay)

        logger.error(f"Task {task_id} did not finish after {max_attempts} attempts")
        return None

    def _make_api_call(self, geojson, dataset, year=None, runasync=None, max_poll_attempts=12):
        """
        Make the stats call. Returns final JSON response containing 'data' or None.
        Follows the WorldPop API pattern: /services/stats?dataset=...&year=...&geojson=...&runasync=...
        If a taskid is returned, polls /tasks/{taskid}.
        """
        year = str(year or self.year)
        # decide runasync if not provided
        if runasync is None:
            runasync = True if len(json.dumps(geojson)) > self.async_threshold else False

        geojson_str = json.dumps(geojson, separators=(",", ":"))
        params = self._build_params(dataset, year, geojson_str, runasync)

        stats_url = f"{self.base_url}/services/stats"
        logger.info(f"Requesting {dataset} for year {year}. runasync={runasync}. URL: {stats_url}")

        try:
            resp = requests.get(stats_url, params=params, timeout=60)
            if resp.status_code == 413:
                logger.error("Initial request returned HTTP 413: payload too large")
                return None
            resp.raise_for_status()
            resp_json = resp.json()
        except requests.RequestException as e:
            logger.error(f"Request exception calling stats: {e}")
            return None

        # If created with a taskid -> poll
        if "taskid" in resp_json:
            task_id = resp_json["taskid"]
            logger.info(f"Got taskid {task_id}. Polling...")
            return self._poll_task(task_id, max_attempts=max_poll_attempts)

        # If data returned immediately (synchronous)
        if "data" in resp_json:
            logger.info("Received direct data in response")
            return resp_json

        logger.error(f"Unexpected response format: {resp_json}")
        return None

    # ---------- save helpers ----------
    def _save_population_data(self, data, district, dataset_name="wpgppop"):
        out = self.output_dir / f"{district}_{dataset_name}_{self.year}.csv"
        # total_population might be nested under data
        total = data.get("data", {}).get("total_population")
        with open(out, "w", newline="") as fh:
            fh.write("district,total_population\n")
            fh.write(f"{district},{total}\n")
        logger.info(f"Saved population totals to {out}")

    def _save_pyramid_data(self, data, district):
        if not data or "data" not in data or "agesexpyramid" not in data["data"]:
            logger.error(f"No agesexpyramid in returned data for {district}. Full response: {data}")
            return
        out = self.output_dir / f"{district}_agesexpyramid_{self.year}.csv"
        rows = data["data"]["agesexpyramid"]
        # Expect rows to be dicts with keys 'class','age','male','female'
        with open(out, "w", newline="") as fh:
            fh.write("class,age,male,female\n")
            for r in rows:
                cls = r.get("class", "")
                age = r.get("age", "")
                male = r.get("male", "")
                female = r.get("female", "")
                fh.write(f"{cls},{age},{male},{female}\n")
        logger.info(f"Saved agesex pyramid to {out}")

    # ---------- public method ----------
    def fetch_worldpop_data(self, geojson_path, dataset="wpgpas", year=None):
        """
        Orchestrates prepare -> API call -> save.
        dataset: 'wpgppop' or 'wpgpas'
        """
        district = Path(geojson_path).stem
        logger.info(f"Processing {district} (dataset={dataset})")
        try:
            geojson, geojson_str = self._prepare_geojson(geojson_path)

            # If even after simplification the payload is large, try an extra simplification pass
            if len(geojson_str) > 8000:
                logger.warning("GeoJSON still large after initial simplify; applying stronger simplify + truncate")
                geojson = self.simplify_geometry(geojson, tolerance=self.simplify_tolerance * 10)
                if self.truncate_precision is None:
                    # choose a safe default truncation if none specified
                    geojson = self.truncate_coordinates(geojson, precision=3)
                geojson_str = json.dumps(geojson, separators=(",", ":"))

            # Make API call
            resp = self._make_api_call(geojson, dataset=dataset, year=year)

            if not resp:
                logger.error(f"No response for {district}")
                return False

            # Save appropriate output
            if dataset == "wpgppop":
                self._save_population_data(resp, district, dataset_name=dataset)
            elif dataset == "wpgpas":
                self._save_pyramid_data(resp, district)
            else:
                logger.warning(f"Unrecognized dataset: {dataset}. Dumping response to json")
                outfile = self.output_dir / f"{district}_{dataset}_{self.year}.json"
                with open(outfile, "w") as fh:
                    json.dump(resp, fh)
                logger.info(f"Wrote raw response to {outfile}")

        except Exception as e:
            logger.exception(f"Error processing {district}: {e}")
            return False
        return True


# ---------- Example CLI / batch runner ----------
def main():
    YEAR = "2020"

    fetcher = WorldPopDataFetcher(
        year=YEAR,
        api_key=None,   # or "YOUR_KEY"
        simplify_tolerance=0.01,
        truncate_precision=3,
        async_threshold=1500,
        output_dir=None,  # let the class use/create .../agesexstructure/2017
    )

    geojson_dir = Path(
        "Sources/WORLDPOP/scraper_data/shapefiles/district_geojson/district_geojson"
    )

    files = list(sorted(geojson_dir.glob("*.geojson")))
    logger.info(f"Found {len(files)} geojson files in {geojson_dir}")

    for gj in files:
        district = gj.stem
        # This is the same naming pattern used in _save_pyramid_data
        expected_csv = fetcher.output_dir / f"{district}_agesexpyramid_{YEAR}.csv"

        if expected_csv.exists():
            logger.info(f"CSV already exists for {district}: {expected_csv} (will OVERWRITE)")
        else:
            logger.info(f"No existing CSV for {district}. A new file will be created at: {expected_csv}")

        logger.info(f"Fetching for: {gj.name}")
        success = fetcher.fetch_worldpop_data(str(gj), dataset="wpgpas", year=YEAR)
        if not success:
            logger.error(f"Failed for {gj.name}")

if __name__ == "__main__":
    main()
