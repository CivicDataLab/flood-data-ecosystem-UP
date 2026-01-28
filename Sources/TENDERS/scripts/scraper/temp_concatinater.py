import pandas as pd
import os
import glob
from time import time

# where you want your final per-month files to go
DATA_PATH = os.path.join(os.getcwd(), 'Sources', 'TENDERS', 'data', 'monthly_tenders')

# where your scraper drops either subfolders or flat CSVs
SCRAPED_PATH = os.path.join(os.getcwd(), 'Sources', 'TENDERS', 'scripts', 'scraper', 'scraped_recent_tenders')

os.makedirs(DATA_PATH, exist_ok=True)

print("CWD:", os.getcwd())
print("DATA_PATH:", DATA_PATH)
print("SCRAPED_PATH:", SCRAPED_PATH)

OUTPUT_COLS = [
    'Tender ID','tender_externalreference','tender_title','Work Description',
    'Tender Category','Tender Type','Form of contract','Product Category',
    'Is Multi Currency Allowed For BOQ','Allow Two Stage Bidding',
    'Independent External Monitor/Remarks','Published Date',
    'Pre Bid Meeting Date','Bid Validity(Days)','Should Allow NDA Tender',
    'Allow Preferential Bidder','Payment Mode','Bid Opening Date',
    'Organisation Chain','location','Pincode','No of Bids Received',
    'Tender Value in ₹','Bidder Name','Awarded Value','Status',
    'Contract Date','Department'
]

RENAME_MAP = {
    'Tender Reference Number': 'tender_externalreference',
    'Tender Ref No':           'tender_externalreference',
    'Title':                   'tender_title',
    'Tender Title':            'tender_title',
    'No. of Covers':           'No of Bids Received',
    'Publish Date':            'Published Date',
    'Location':                'location',
}

def dedupe_columns_keep_first(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.duplicated(keep='first')].copy()

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.astype(str).str.strip()
    df.columns = df.columns.str.replace(r'\s*:\s*$', '', regex=True)  # "Contract Date :" -> "Contract Date"

    # normalize underscore/casing variants to a single "Contract Date"
    norm = df.columns.str.lower().str.replace(' ', '_')
    colmap = dict(zip(norm, df.columns))
    if 'contract_date' in colmap:
        df = df.rename(columns={colmap['contract_date']: 'Contract Date'})

    # titles/refs
    df = df.rename(columns=RENAME_MAP)

    # org spelling
    if 'Organization Chain' in df.columns and 'Organisation Chain' not in df.columns:
        df = df.rename(columns={'Organization Chain': 'Organisation Chain'})

    return df

def clean_date_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.replace('\u00a0', ' ', regex=False).str.strip()
    s = s.replace({'': pd.NA, 'nan': pd.NA, 'None': pd.NA, 'NaN': pd.NA})
    return s

def process_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    df = dedupe_columns_keep_first(df)

    # ---- FIX: empty strings are not NA, so drop them explicitly ----
    if 'Tender ID' not in df.columns:
        df['Tender ID'] = pd.NA
    df['Tender ID'] = df['Tender ID'].astype(str).str.replace('\u00a0', ' ', regex=False).str.strip()
    df.loc[df['Tender ID'].isin(['', 'nan', 'None', 'NaN']), 'Tender ID'] = pd.NA
    df = df.dropna(subset=['Tender ID'])

    # department
    if 'Organisation Chain' in df.columns:
        df['Department'] = df['Organisation Chain']
    else:
        df['Organisation Chain'] = pd.NA
        df['Department'] = pd.NA

    # parse contract date
    if 'Contract Date' in df.columns:
        raw = clean_date_series(df['Contract Date'])
        dt = pd.to_datetime(raw, dayfirst=True, errors='coerce')
        df['Contract Date'] = dt
        df['year_month'] = dt.dt.strftime('%Y_%m')
    else:
        df['Contract Date'] = pd.NaT
        df['year_month'] = pd.NA

    # ensure all OUTPUT_COLS exist
    for col in OUTPUT_COLS:
        if col not in df.columns:
            df[col] = pd.NA

    return df[OUTPUT_COLS + ['year_month']]


def append_month_csv(out_path: str, chunk: pd.DataFrame):
    exists = os.path.exists(out_path)
    chunk.to_csv(out_path, mode='a', header=not exists, index=False)

# ---- STREAMING WRITE ----
REPORT_EVERY = 200
t0 = time()

all_csvs = glob.glob(os.path.join(SCRAPED_PATH, '**', '*.csv'), recursive=True)
print("Total CSVs found:", len(all_csvs))

written_rows = 0
missing_rows = 0
months_touched = set()

missing_out = os.path.join(DATA_PATH, '_missing_contract_date.csv')
if os.path.exists(missing_out):
    os.remove(missing_out)  # fresh run

for i, csv_path in enumerate(all_csvs, start=1):
    if i == 1 or i % REPORT_EVERY == 0:
        elapsed = time() - t0
        rate = i / elapsed if elapsed > 0 else 0
        print(
            f"[{i}/{len(all_csvs)}] touched_months={len(months_touched)} "
            f"written_rows={written_rows} missing_rows={missing_rows} rate={rate:.1f} files/s "
            f"last={os.path.basename(csv_path)}"
        )

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    df = dedupe_columns_keep_first(df)
    df = process_frame(df)

    # missing dates -> audit file (append)
    miss = df[df['year_month'].isna() | (df['year_month'] == '')].drop(columns=['year_month'])
    if len(miss):
        append_month_csv(missing_out, miss)
        missing_rows += len(miss)

    # valid -> append to month files
    valid = df.dropna(subset=['year_month'])
    valid = valid[valid['year_month'] != '']

    for ym, g in valid.groupby('year_month', sort=False):
        out_file = os.path.join(DATA_PATH, f"{ym}_tenders.csv")
        append_month_csv(out_file, g.drop(columns=['year_month']))
        months_touched.add(ym)
        written_rows += len(g)

print(f"Done. Months written: {len(months_touched)} | rows written: {written_rows} | missing-date rows: {missing_rows}")
