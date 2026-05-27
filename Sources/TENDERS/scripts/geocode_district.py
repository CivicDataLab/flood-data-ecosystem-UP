import pandas as pd
import geopandas as gpd
import re
import os
from difflib import SequenceMatcher

tenders_df = pd.read_csv(os.getcwd()+'/Sources/TENDERS/data/flood_tenders_all.csv')
UP_VILLAGES = pd.read_csv(os.getcwd()+ '/Maps/up_ids-drr_shapefiles/UP_VILLAGES_MASTER.csv', encoding='utf-8').dropna()

# Clean village names
up_villages = UP_VILLAGES["vilnam_soi"]
village_duplicates_df = UP_VILLAGES[up_villages.isin(up_villages[up_villages.duplicated()])].sort_values("vilnam_soi")

locations = []
for idx, row in tenders_df.iterrows():
    LOCATION = str(row['location']).lower()
    LOCATION = LOCATION.replace('village','')
    LOCATION = LOCATION.replace('district','')
    LOCATION = LOCATION.replace('dist','')
    LOCATION = re.sub(r'[^a-zA-Z\n\.]', ' ', LOCATION)
    scores = []
    for subdistrict in UP_VILLAGES.sdtname.dropna().unique():
        score = SequenceMatcher(None, LOCATION, subdistrict.lower().strip()).ratio()
        scores.append(score)
    if max(scores) > 0.8:
        locations.append(UP_VILLAGES.sdtname.dropna().unique()[scores.index(max(scores))])
    else:
        locations.append(row['location'])

tenders_df['location'] = locations

# GEOCODE DISTRICTS
# Make dictionaries for sub-districts and villages mapped to districts
UP_subdist_dict = UP_VILLAGES[['sdtname','dtname']].dropna().drop_duplicates().drop_duplicates(['sdtname'], keep=False).set_index('sdtname').to_dict(orient='index')
UP_VILLAGES_dict = UP_VILLAGES[['vilnam_soi','dtname']].drop_duplicates(['vilnam_soi'], keep=False).set_index('vilnam_soi').to_dict(orient='index')

# Districts list
up_districts = list(set(UP_VILLAGES.dtname.dropna()))

# Sub-districts list (non-repeating)
up_sub_districts = list(set(UP_subdist_dict.keys()))

# Villages list (non-repeating)
up_villages_list = list(set(UP_VILLAGES_dict.keys()))

# METHOD 1 - GET TENDER DISTRICT BASED ON externalReference COLUMN
tenders_df['tender_district_externalReference'] = None
for idx, row in tenders_df.iterrows():
    tender_slug = str(row['tender_externalreference'])
    tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug)
    for district in up_districts:
        if re.findall(r'\b%s\b' % district.lower().strip(), tender_slug.lower()):
            tenders_df.loc[idx, 'tender_district_externalReference'] = district
            break

## SUB DISTRICT
for idx, row in tenders_df.iterrows():
    if row['tender_district_externalReference'] is not None:
        continue
    tender_slug = str(row['tender_externalreference'])
    tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug)
    for sub_district in up_sub_districts:
        if re.findall(r'\b%s\b' % sub_district.lower(), tender_slug.lower()):
            tenders_df.loc[idx, 'tender_district_externalReference'] = UP_subdist_dict[sub_district]['dtname']
            break

# METHOD 2 - GET TENDER DISTRICT BASED ON TITLE AND WORK DESCRIPTION
tenders_df['tender_district_title_description'] = None
for idx, row in tenders_df.iterrows():
    tender_slug = str(row['tender_title']) + ' ' + str(row['Work Description'])
    tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug)
    for district in up_districts:
        if re.findall(r'\b%s\b' % district.lower().strip(), tender_slug.lower()):
            tenders_df.loc[idx, 'tender_district_title_description'] = district
            break

## SUB DISTRICT
for idx, row in tenders_df.iterrows():
    if row['tender_district_title_description'] is not None:
        continue
    tender_slug = str(row['tender_title']) + ' ' + str(row['Work Description'])
    tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug)
    for sub_district in up_sub_districts:
        if re.findall(r'\b%s\b' % sub_district.lower(), tender_slug.lower()):
            tenders_df.loc[idx, 'tender_district_title_description'] = UP_subdist_dict[sub_district]['dtname']
            break

# METHOD 3 - GET TENDER DISTRICT BASED ON LOCATION COLUMN
tenders_df['tender_district_location'] = None
for idx, row in tenders_df.iterrows():
    tender_slug = str(row['location'])
    tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug)
    for district in up_districts:
        if re.findall(r'\b%s\b' % district.lower().strip(), tender_slug.lower()):
            tenders_df.loc[idx, 'tender_district_location'] = district
            break

## SUB DISTRICT
for idx, row in tenders_df.iterrows():
    if row['tender_district_location'] is not None:
        continue
    tender_slug = str(row['location'])
    tender_slug = re.sub(r'[^a-zA-Z0-9 \n\.]', ' ', tender_slug)
    for sub_district in up_sub_districts:
        if re.findall(r'\b%s\b' % sub_district.lower(), tender_slug.lower()):
            tenders_df.loc[idx, 'tender_district_location'] = UP_subdist_dict[sub_district]['dtname']
            break

# WEIGHTAGE LOGIC
tenders_df['tender_district_externalReference'].fillna('NA', inplace=True)
tenders_df['tender_district_title_description'].fillna('NA', inplace=True)
tenders_df['tender_district_location'].fillna('NA', inplace=True)

tenders_df['DISTRICT_FINALISED'] = ''

for idx, row in tenders_df.iterrows():
    district1 = row['tender_district_externalReference']
    district2 = row['tender_district_title_description']
    district3 = row['tender_district_location']
    districts = [district1, district2, district3]
    districts = set([x for x in districts if x != 'NA'])

    if len(districts) == 1:
        DISTRICT_SELECTED = list(districts)[0]
    elif len(districts) == 0:
        DISTRICT_SELECTED = 'NA'
    else:
        DISTRICT_SELECTED = 'CONFLICT'

    tenders_df.loc[idx, 'DISTRICT_FINALISED'] = DISTRICT_SELECTED

tenders_df.to_csv(os.getcwd()+'/Sources/TENDERS/data/floodtenders_districtgeotagged.csv', index=False)

print('Total number of flood related tenders: ', tenders_df.shape[0])
print('Number of tenders whose district could not be geo-tagged: ', tenders_df[tenders_df['DISTRICT_FINALISED']=='NA'].shape[0])
print('Number of tenders whose district identification is a CONFLICT: ', tenders_df[tenders_df['DISTRICT_FINALISED']=='CONFLICT'].shape[0])