import pandas as pd
import os
import glob

# where you want your final per‐month files to go
DATA_PATH = os.path.join(os.getcwd(), 'Sources', 'TENDERS', 'data', 'monthly_tenders')

# where your scraper drops either subfolders or flat CSVs
SCRAPED_PATH = os.path.join(os.getcwd(), 'Sources', 'TENDERS', 'scripts',
                            'scraper', 'scraped_recent_tenders')

# the canonical columns & order for your outputs
OUTPUT_COLS = [
    'Tender ID','tender_externalreference','tender_title','Work Description',
    'Tender Category','Tender Type','Form of contract','Product Category',
    'Is Multi Currency Allowed For BOQ','Allow Two Stage Bidding',
    'Independent External Monitor/Remarks','Published Date',
    'Pre Bid Meeting Date','Bid Validity(Days)','Should Allow NDA Tender',
    'Allow Preferential Bidder','Payment Mode','Bid Opening Date',
    'Organisation Chain','location','Pincode','No of Bids Received',
    'Tender Value in ₹','Bidder Name','Awarded Value','Status',
    'Contract Date :','Department'
]

def process_frame(df):
    # normalize column names
    df.columns = df.columns.str.strip()
    # drop rows missing the one critical key
    df = df.dropna(subset=['Tender ID'])
    # parse contract date if present
    if 'Contract Date' in df.columns:
        df['Contract Date'] = pd.to_datetime(
            df['Contract Date'], dayfirst=True, errors='coerce'
        )
        df['year_month'] = df['Contract Date'].dt.strftime('%Y_%m')
    else:
        # fallback: all in one bucket (unlikely here)
        df['year_month'] = 'unknown'
    # department
    if 'Organisation Chain' in df.columns:
        df['Department'] = df['Organisation Chain']
    elif 'Organization Chain' in df.columns:
        df['Department'] = df['Organization Chain']
        df = df.rename(columns={'Organization Chain':'Organisation Chain'})
    else:
        df['Department'] = pd.NA

    # rename references & titles
    df = df.rename(columns={
        'Tender Reference Number': 'tender_externalreference',
        'Tender Ref No':               'tender_externalreference',
        'Title':                       'tender_title',
        'Tender Title':                'tender_title',
        'No. of Covers':              'No of Bids Received',
        'Publish Date':                'Published Date',
        'Location':                    'location'
    })

    # ensure all OUTPUT_COLS exist
    for col in OUTPUT_COLS:
        if col not in df.columns:
            df[col] = pd.NA

    # reorder & return
    return df[OUTPUT_COLS + ['year_month']]

# 1️⃣ Handle any “flat” CSVs in SCRAPED_PATH
for csv_path in glob.glob(os.path.join(SCRAPED_PATH, '*.csv')):
    df = pd.read_csv(csv_path, dtype=str)
    df = process_frame(df)

    for ym, group in df.groupby('year_month'):
        out_file = os.path.join(DATA_PATH, f'{ym}_tenders.csv')
        group.drop(columns=['year_month']) \
             .to_csv(out_file, index=False)
        print(f'Wrote {len(group)} tenders → {os.path.basename(out_file)}')

# 2️⃣ Fall back to your existing year/month‐folder logic
for year in range(2020, 2021):
    for month in range(1, 4):
        ym = f"{year}_{month:02d}"
        folder = os.path.join(SCRAPED_PATH, ym)
        csvs = glob.glob(os.path.join(folder, '*.csv'))
        if not csvs:
            continue
        # stack them
        dfs = [pd.read_csv(f, dtype=str) for f in csvs]
        master = pd.concat(dfs, ignore_index=True)
        master = process_frame(master)

        out_file = os.path.join(DATA_PATH, f'{ym}_tenders.csv')
        master.drop(columns=['year_month']) \
              .to_csv(out_file, index=False)
        print(f'Wrote {len(master)} tenders → {os.path.basename(out_file)}')
