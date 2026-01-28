import pandas as pd
import os
import re
import numpy as np
import glob

# input_df - after the scraper code is run
data_path = os.getcwd() + r'/Sources/TENDERS/data/monthly_tenders/'
print("Data path: ", data_path)

OUT_DIR = os.path.join(os.getcwd(), 'Sources', 'TENDERS', 'data', 'flood_tenders')
os.makedirs(OUT_DIR, exist_ok=True)

def safe_str(x) -> str:
    """Convert NaN/None to empty string, else string."""
    if pd.isna(x):
        return ""
    return str(x)

def populate_keyword_dict(keyword_list):
    return {keyword: 0 for keyword in keyword_list}

# Flood Keywords
POSITIVE_KEYWORDS = [
    'Flood', 'Embankment', 'embkt', 'Relief', 'Erosion', 'SDRF', 'Inundation', 'Hydrology',
    'Silt', 'Siltation', 'Bund', 'Trench', 'Breach', 'Culvert', 'Sluice', 'Dyke',
    'Storm water drain', 'Emergency', 'Immediate', 'IM', 'AE', 'A E', 'AAPDA MITRA',
    'Bridge', "River", "Drain", 'Restoration', 'Protection', 'irr', 'irrigation', 'dam',
    'Nallah', 'Retrofitting', 'Pond', 'Pokhari', 'D/C', 'Recharge shaft', 'LFB', 'RFB'
]
NEGATIVE_KEYWORDS = ['Floodlight', 'Flood Light', 'GAS', 'FIFA', 'pipe', 'pipes', 'covid', 'supply', 'Beautification', 'Installation']

def flood_filter(row):
    """
    :return: Tuple of (is_flood_tender, positive_kw_dict, negative_kw_dict)
    """
    positive_keywords_dict = populate_keyword_dict(POSITIVE_KEYWORDS)
    negative_keywords_dict = populate_keyword_dict(NEGATIVE_KEYWORDS)

    tender_slug = f"{safe_str(row.get('tender_externalreference'))} {safe_str(row.get('tender_title'))} {safe_str(row.get('Work Description'))}"
    tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug).lower()

    is_flood_tender = False

    for keyword in POSITIVE_KEYWORDS:
        kw = re.escape(keyword.lower())
        keyword_count = len(re.findall(rf"\b{kw}\b", tender_slug))
        positive_keywords_dict[keyword] = keyword_count
        if keyword_count > 0:
            is_flood_tender = True

    for keyword in NEGATIVE_KEYWORDS:
        kw = re.escape(keyword.lower())
        keyword_count = len(re.findall(rf"\b{kw}\b", tender_slug))
        negative_keywords_dict[keyword] = keyword_count
        if keyword_count > 0:
            is_flood_tender = False

    return str(is_flood_tender), str(positive_keywords_dict), str(negative_keywords_dict)

csvs = glob.glob(os.path.join(data_path, '*.csv'))

for csv in csvs:
    filename = os.path.basename(csv)
    print("FILENAME", filename)

    input_df = pd.read_csv(csv, dtype=str)  # keep as strings where possible
    # Ensure expected cols exist (avoid KeyError surprises)
    for col in ["tender_externalreference", "tender_title", "Work Description", "Department", "Contract Date", "Tender ID"]:
        if col not in input_df.columns:
            input_df[col] = pd.NA

    # Optional: drop blank Tender ID rows if they exist
    input_df["Tender ID"] = input_df["Tender ID"].astype(str).str.strip()
    input_df.loc[input_df["Tender ID"].isin(["", "nan", "None", "NaN"]), "Tender ID"] = pd.NA
    input_df = input_df.dropna(subset=["Tender ID"]).copy()
    input_df = input_df.loc[input_df['Status']== "Accepted-AOC"]

    flood_filter_tuples = input_df.apply(flood_filter, axis=1)
    input_df.loc[:, 'is_flood_tender'] = [var[0] for var in list(flood_filter_tuples)]
    input_df.loc[:, 'positive_keywords_dict'] = [var[1] for var in list(flood_filter_tuples)]
    input_df.loc[:, 'negative_keywords_dict'] = [var[2] for var in list(flood_filter_tuples)]

    # Removing tenders from certain departments that are not related to flood management.
    tenders_df = input_df[
        (input_df.is_flood_tender == 'True') &
        (~input_df.Department.isin(["Directorate of Agriculture and Assam Seed Corporation", "Department of Handloom Textile and Sericulture"]))
    ].copy()  # <-- .copy() kills the SettingWithCopyWarning

    print('Number of flood related tenders filtered: ', tenders_df.shape[0])
    if tenders_df.shape[0] == 0:
        continue

    # ---- Season classification (vectorized, no iterrows, no drop-inplace) ----
    # NOTE: Your comment says "Should be Published Date" but you use Contract Date.
    # Keeping Contract Date as-is to match your current logic.
    tenders_df["Contract Date"] = pd.to_datetime(tenders_df["Contract Date"], errors="coerce", dayfirst=True)

    # Drop rows where date couldn't be parsed
    tenders_df = tenders_df[tenders_df["Contract Date"].notna()].copy()

    months = tenders_df["Contract Date"].dt.month
    tenders_df["Season"] = np.select(
        [
            months.between(3, 5),
            months.between(6, 9)
        ],
        [
            "Pre-Monsoon",
            "Monsoon"
        ],
        default="Post-Monsoon"
    )

    # ---- identify scheme related information ----
    scheme_kw = {'ridf', 'sdrf', 'sopd', 'cidf', 'ltif', 'sdmf', 'ndrf'}
    schemes_identified = []

    for _, row in tenders_df.iterrows():
        tender_slug = f"{safe_str(row.get('tender_title'))} {safe_str(row.get('tender_externalreference'))} {safe_str(row.get('Work Description'))}"
        tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug).lower()
        tokens = set(re.split(r'[-.,()_\s/]\s*', tender_slug))
        hit = list(tokens & scheme_kw)
        schemes_identified.append(hit[0].upper() if hit else '')

    tenders_df.loc[:, 'Scheme'] = schemes_identified

    # ---- EROSION RELATED TENDERS ----
    EROSION_KEYWORDS = ['anti erosion', 'ae', 'a/e', 'a e', 'erosion', 'eroded', 'erroded', 'errosion']
    for index, row in tenders_df.iterrows():
        tender_slug = f"{safe_str(row.get('tender_externalreference'))} {safe_str(row.get('tender_title'))} {safe_str(row.get('Work Description'))}"
        tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug).lower()
        is_present = [len(re.findall(rf"\b{re.escape(kw.lower())}\b", tender_slug)) for kw in EROSION_KEYWORDS]
        tenders_df.loc[index, "Erosion"] = (sum(is_present) > 0)

    # ---- ROADS, BRIDGES, EMBANKMENTS ----
    ROADS_BRIDGES_EMBANKMENTS_KEYWORDS = [
        'roads', 'bridges', 'road', 'bridge', 'storm water drain', 'drain',
        'box cul', 'box culvert', 'box culv', 'culvert', 'embankment', 'embkt',
        'river bank protection', 'bund', 'bunds', 'bundh', 'bank protection', 'dyke',
        'dyke wall', 'dyke walls', 'silt', 'siltation', 'sluice', 'breach'
    ]
    for index, row in tenders_df.iterrows():
        tender_slug = f"{safe_str(row.get('tender_externalreference'))} {safe_str(row.get('tender_title'))} {safe_str(row.get('Work Description'))}"
        tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug).lower()
        is_present = [len(re.findall(rf"\b{re.escape(kw.lower())}\b", tender_slug)) for kw in ROADS_BRIDGES_EMBANKMENTS_KEYWORDS]
        tenders_df.loc[index, "Roads_Bridges_Embkt"] = (sum(is_present) > 0)

    # ---- Response Type classification ----
    IMMEDIATE_MEASURES_KEYWORDS = ['sdrf','im','i/m','gr','g/r','relief','package','pkt','immediate', 'emergency', 'pk', 'g.r.', 'i.m.']
    REPAIR_RESTORATION_IMPROVEMENTS_KEYWORDS = [
        'improvement', 'imp.', 'impvt', 'impt.', 'repair', 'repairing', 'restoration',
        'reconstruction', 'reconstn', 'recoupment', 'raising', 'strengthening', 'r/s',
        'm and r', 'upgradation', 'renovation', 'repairing/renovation', 'up-gradation',
        'm-r', 'm-r ', 'mr', 'widening', 'r s', 'extension', 'replacement', 're-shaping',
        're-grading', 'Check Dam','Construction','Bridge','Retrofitting','Drain'
    ]
    PREPAREDNESS_KEYWORDS = [
        'shelter', 'shelters', 'tarpaulin', 'shelter ',
        'responder kit', 'aapda mitra volunteers','aapda mitra volunteer', 'district emergency stockpile', 'search light',
        'life buoys', 'boat ambulances', 'boat ambulance', 'inflatable rubber',
        'mechanized boats', 'mechanised boats','mechanized boat', 'mechanised boat',
        'per','Period','Periodical maintainance','Maintainance','Annual maintenance','Protection','scoured','Scoured bank',
        'Recharge Shaft','De-weeding','Cleaning ','Flood Protection work'
    ]

    for index, row in tenders_df.iterrows():
        immedidate_measures_dict = populate_keyword_dict(IMMEDIATE_MEASURES_KEYWORDS)
        repair_restoration_dict = populate_keyword_dict(REPAIR_RESTORATION_IMPROVEMENTS_KEYWORDS)
        preparedness_measures_dict = populate_keyword_dict(PREPAREDNESS_KEYWORDS)

        response_type = "Others"
        tender_slug = f"{safe_str(row.get('tender_externalreference'))} {safe_str(row.get('tender_title'))} {safe_str(row.get('Work Description'))}"
        tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug).lower()

        for keyword in immedidate_measures_dict:
            kw = re.escape(keyword.lower())
            keyword_count = len(re.findall(rf"\b{kw}\b", tender_slug))
            immedidate_measures_dict[keyword] = keyword_count if keyword_count else False
            if keyword_count:
                response_type = "Immediate Measures"

        for keyword in repair_restoration_dict:
            kw = re.escape(keyword.lower())
            keyword_count = len(re.findall(rf"\b{kw}\b", tender_slug))
            repair_restoration_dict[keyword] = keyword_count if keyword_count else False
            if keyword_count:
                response_type = "Repair and Restoration"

        for keyword in preparedness_measures_dict:
            kw = re.escape(keyword.lower())
            keyword_count = len(re.findall(rf"\b{kw}\b", tender_slug))
            preparedness_measures_dict[keyword] = keyword_count if keyword_count else False
            if keyword_count and response_type == "Others":
                response_type = "Preparedness Measures"

        tenders_df.loc[index, "Response Type"] = response_type

        if response_type == "Immediate Measures":
            sub_head_dict = {k: v for k, v in immedidate_measures_dict.items() if v is not False}
            tenders_df.loc[index, "Flood Response - Subhead"] = str(sub_head_dict)
        elif response_type == "Repair and Restoration":
            sub_head_dict = {k: v for k, v in repair_restoration_dict.items() if v is not False}
            tenders_df.loc[index, "Flood Response - Subhead"] = str(sub_head_dict)
        elif response_type == "Preparedness Measures":
            sub_head_dict = {k: v for k, v in preparedness_measures_dict.items() if v is not False}
            tenders_df.loc[index, "Flood Response - Subhead"] = str(sub_head_dict)

    out_path = os.path.join(OUT_DIR, filename)
    print("Writing:", out_path)
    tenders_df.to_csv(out_path, encoding='utf-8', index=False)

# ---- Combine all flood tenders into one file ----
data_path2 = os.path.join(os.getcwd(), 'Sources', 'TENDERS', 'data')
csvs2 = glob.glob(os.path.join(data_path2, 'flood_tenders', '*.csv'))
print("Found flood files:", csvs2)

dfs = []
for f in csvs2:
    base = os.path.basename(f)

    # Extract YYYY_MM from filename (works for 2018_06_tenders.csv and 2020_01.csv)
    m = re.search(r'(\d{4}_\d{2})', base)
    month = m.group(1) if m else base[:7]

    df = pd.read_csv(f, dtype=str)
    df['month'] = month
    dfs.append(df)

if dfs:
    tenders_all = pd.concat(dfs, ignore_index=True)
    out_all = os.path.join(data_path2, 'flood_tenders_all.csv')
    tenders_all.to_csv(out_all, index=False)
    print("Wrote:", out_all)
else:
    print("No flood tenders files found to combine.")
