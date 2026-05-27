import pandas as pd
import os
import re
import geopandas as gpd
from tqdm import tqdm 
import warnings
warnings.filterwarnings("ignore")

UP_VILLAGES = pd.read_csv(os.getcwd()+'/Maps/up_ids-drr_shapefiles/UP_VILLAGES_MASTER.csv', encoding='utf-8').dropna()
UP_BLOCKS = gpd.read_file(os.getcwd()+'/Maps/up_ids-drr_shapefiles/UP_subdistrict_final_4326.geojson', driver='GeoJSON')
UP_VILLAGES['object_id'] = UP_VILLAGES['stcode11'].astype(str) + '-' + UP_VILLAGES['dtcode11'].astype(str) + '-' + UP_VILLAGES['sdtcode11'].astype(str)

tenders_df = pd.read_csv(os.getcwd()+'/Sources/TENDERS/data/floodtenders_districtgeotagged.csv', keep_default_na=False)

MASTER_DFs = []
for FOCUS_DISTRICT in tqdm(UP_VILLAGES.dtname.unique()):
    # Create dictionaries for FOCUS DISTRICT
    FOCUSDIST_village_dict = {}
    FOCUSDIST_subdistrict_dict = {}
    FOCUSDIST_gp_dict = {}
    FOCUSDIST_district_dict = {}

    for index, row in UP_VILLAGES[UP_VILLAGES.dtname == FOCUS_DISTRICT].iterrows():
        # VILLAGES
        if row["vilnam_soi"]:
            village_name = re.sub(r'[^a-zA-Z]', "", row["vilnam_soi"])
            FOCUSDIST_village_dict[village_name] = {
                "village_id": row["vilcode11"],
                "sdtname": row["sdtname"],
                "gp_name": row["gp_name"],
                "dtname": row["dtname"]
            }

        # SUBDISTRICTS
        FOCUSDIST_subdistrict_dict[row["sdtname"]] = {
            "subdistrict": row["sdtname"],
            "gp_name": row["gp_name"],
            "dtname": row["dtname"]
        }

        # GP
        FOCUSDIST_gp_dict[row["gp_name"]] = {"dtname": row["dtname"]}

        # DISTRICT
        FOCUSDIST_district_dict[row["dtname"]] = True

    # Remove generic village names
    for name in ['RIVER', 'NO', 'TOWN']:
        try:
            del FOCUSDIST_village_dict[name]
        except:
            pass

    FOCUSDIST_villages = list(FOCUSDIST_village_dict.keys())
    FOCUSDIST_subdistricts = list(FOCUSDIST_subdistrict_dict.keys())
    FOCUSDIST_gp = list(FOCUSDIST_gp_dict.keys())

    # GEO-CODE VILLAGES, SUBDISTRICTS, GPs
    tenders_df_FOCUSDISTRICT = tenders_df[tenders_df["DISTRICT_FINALISED"] == FOCUS_DISTRICT].copy()

    for idx, row in tenders_df_FOCUSDISTRICT.iterrows():
        tender_villages = []
        tender_village_id = ""
        tender_subdistrict = ""
        tender_subdistrict_location = ""
        tender_gp = ""

        tender_slug = str(row['tender_externalreference']) + ' ' + str(row['tender_title']) + ' ' + str(row['Work Description'])
        tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug)

        # Pattern for removing unwanted substrings
        substrings_to_remove = ["(pt)", "\n"]
        base_pattern = "|".join(map(re.escape, substrings_to_remove))

        # MATCH VILLAGES
        for village in FOCUSDIST_villages:
            if not re.search(r'[a-zA-Z]', village):
                continue
            village = re.sub(r"[\[\]]?", "", village)
            village_search = village.lower()
            village_search = re.sub(base_pattern, " ", village_search)

            if re.findall(r'\b%s\b' % village_search.strip(), tender_slug.lower()):
                tender_villages.append(village)
                tender_village_id = FOCUSDIST_village_dict[village]['village_id']
                tender_subdistrict = FOCUSDIST_village_dict[village]['sdtname']

        # MATCH SUBDISTRICTS
        for subdistrict in FOCUSDIST_subdistricts:
            subdistrict_search = subdistrict.lower()
            subdistrict_search = re.sub(base_pattern, " ", subdistrict_search)
            if re.findall(r'\b%s\b' % subdistrict_search.strip(), tender_slug.lower()):
                tender_subdistrict = subdistrict
                tender_subdistrict_location = subdistrict
                tender_gp = FOCUSDIST_subdistrict_dict[subdistrict]['gp_name']
                break

        # MATCH GPs
        for gp in FOCUSDIST_gp:
            gp_search = gp.lower()
            gp_search = re.sub(base_pattern, " ", gp_search)
            gp_pattern = r'\b{}\b'.format(re.escape(gp_search.strip()))
            if re.search(gp_pattern, tender_slug, flags=re.IGNORECASE):
                tender_gp = gp
                break

        tenders_df_FOCUSDISTRICT.loc[idx, 'tender_villages'] = str(tender_villages)[1:-1]
        tenders_df_FOCUSDISTRICT.loc[idx, 'tender_subdistrict'] = tender_subdistrict
        tenders_df_FOCUSDISTRICT.loc[idx, 'tender_subdistrict_location'] = tender_subdistrict_location
        tenders_df_FOCUSDISTRICT.loc[idx, 'gp'] = tender_gp

    MASTER_DFs.append(tenders_df_FOCUSDISTRICT)

MASTER_DFs.append(tenders_df[tenders_df["DISTRICT_FINALISED"] == 'NA'])
MASTER_DFs.append(tenders_df[tenders_df["DISTRICT_FINALISED"] == 'CONFLICT'])

MASTER_DF = pd.concat(MASTER_DFs)

# Subdistrict Finalisation
MASTER_DF['SUBDISTRICT_FINALISED'] = ''
for idx, row in MASTER_DF.iterrows():
    MASTER_DF.loc[idx, 'SUBDISTRICT_FINALISED'] = row['tender_subdistrict_location']

    if row['tender_subdistrict_location'] == '':
        MASTER_DF.loc[idx, 'SUBDISTRICT_FINALISED'] = row['tender_subdistrict']

    if row['tender_subdistrict_location'] == row['tender_subdistrict']:
        MASTER_DF.loc[idx, 'SUBDISTRICT_FINALISED'] = row['tender_subdistrict']

MASTER_DF.to_csv(os.getcwd()+'/Sources/TENDERS/data/floodtenders_subdistrictgeotagged.csv', index=False)