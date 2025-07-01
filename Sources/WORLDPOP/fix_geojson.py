#!/usr/bin/env python3

import json
import sys
from shapely.geometry import shape, mapping, Polygon, MultiPolygon

def fix_geometry(geom):
    if geom.geom_type == "Polygon":
        # Use only the outer shell, discard holes
        shell = geom.exterior
        fixed = Polygon(shell)
        if not fixed.is_valid:
            fixed = fixed.buffer(0)
        return fixed

    elif geom.geom_type == "MultiPolygon":
        fixed_polygons = []
        for poly in geom.geoms:
            shell = poly.exterior
            fixed = Polygon(shell)
            if not fixed.is_valid:
                fixed = fixed.buffer(0)
            fixed_polygons.append(fixed)
        return MultiPolygon(fixed_polygons)

    else:
        return geom  # No fix needed

def main(infile, outfile):
    with open(infile, "r") as f:
        data = json.load(f)

    fixed_features = []
    for feature in data["features"]:
        geom = shape(feature["geometry"])
        fixed_geom = fix_geometry(geom)
        feature["geometry"] = mapping(fixed_geom)
        fixed_features.append(feature)

    with open(outfile, "w") as f:
        json.dump({
            "type": "FeatureCollection",
            "features": fixed_features
        }, f, indent=2)

    print(f"Fixed GeoJSON written to {outfile}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fix_invalid_geojson.py input.geojson output.geojson")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
