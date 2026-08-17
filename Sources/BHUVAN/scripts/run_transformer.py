import glob
import os
import subprocess

cwd = os.getcwd()
path = cwd + "/Sources/BHUVAN/"
script_path = cwd + "/Sources/BHUVAN/scripts/transformer.py"
PY = "/Users/stephensmathew/anaconda3/envs/flood_env/bin/python"

print(path)

for year in [2026]:
    print(f"\nYear: {year}")
    year = str(year)

    for month in ["07"]:

        # Pattern: YYYY_DD_MM_HH → e.g. 2025_31_08_18_watermarkremoved.tif
        files = glob.glob(
            path + f"data/tiffs/removed_watermarks/{year}_??_{month}_??_watermarkremoved.tif"
        )
        # Edge case: no-hour files like 2025_20_08_watermarkremoved.tif
        files_no_hour = glob.glob(
            path + f"data/tiffs/removed_watermarks/{year}_??_{month}_watermarkremoved.tif"
        )
        files = files + files_no_hour

        if len(files) == 0:
            print(f"  No files for month {month}/{year}, skipping.")
            continue

        print(f"\n  Month {month}/{year} → {len(files)} file(s) found:")
        for f in sorted(files):
            print(f"    {os.path.basename(f)}")

        subprocess.call([PY, script_path, year, month])