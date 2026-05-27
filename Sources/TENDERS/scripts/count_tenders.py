import pandas as pd
import glob

# Path to the monthly_tenders folder
folder = 'Sources/TENDERS/data/monthly_tenders/'

# Get all CSV files in the folder
csv_files = glob.glob(folder + '*.csv')

total_count = 0
accepted_count = 0

for file in csv_files:
    try:
        df = pd.read_csv(file)
        total_count += len(df)
        if 'Status' in df.columns:
            accepted_count += (df['Status'] == 'Accepted-AOC').sum()
    except Exception as e:
        print(f'Error reading {file}: {e}')

print(f'Total number of tenders (all files): {total_count}')
print(f'Total number of tenders with Status="Accepted-AOC": {accepted_count}')
