import subprocess
import os
from datetime import date, timedelta


cwd = os.getcwd()
script_path = cwd + "/Sources/TENDERS/scripts/scraper/scraper_up_recent_tenders_tender_status.py"

# OCT - Dec 2025
for month in range(11, 13):
    subprocess.call(["/Users/stephensmathew/anaconda3/envs/tenderenv/bin/python", 
                    script_path, "2025", str(month)])

# Jan - April 2026
#for month in range(1, 5):
    #subprocess.call(["/Users/stephensmathew/anaconda3/envs/tenderenv/bin/python", 
                  # script_path, "2026", str(month)])

