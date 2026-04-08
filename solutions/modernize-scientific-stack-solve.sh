#!/bin/bash
set -e

pip install numpy pandas matplotlib scipy

# First, let's see what files exist
ls -la /app/

# Look at the original Python 2.7 script if it exists
cat /app/*.py 2>/dev/null || true

# Look at CSV files
find /app -name "*.csv" -exec head -5 {} \;

# Create requirements.txt
cat > /app/requirements.txt << 'EOF'
numpy
pandas
matplotlib
scipy
EOF

# Create the modern Python 3 script
cat > /app/analyze_climate_modern.py << 'PYEOF'
import pandas as pd
import numpy as np
import os
import glob

# Find CSV files in /app
csv_files = glob.glob("/app/*.csv") + glob.glob("/app/data/*.csv")

if not csv_files:
    # Try reading from a known location
    csv_files = glob.glob("/app/**/*.csv", recursive=True)

print(f"Found CSV files: {csv_files}")

# Read and concatenate all CSV data
dfs = []
for f in csv_files:
    try:
        df = pd.read_csv(f)
        dfs.append(df)
        print(f"Read {f}: {len(df)} rows, columns: {list(df.columns)}")
    except Exception as e:
        print(f"Error reading {f}: {e}")

if dfs:
    data = pd.concat(dfs, ignore_index=True)
else:
    raise RuntimeError("No CSV data found")

# Find station and temperature columns (flexible naming)
station_col = None
temp_col = None
for col in data.columns:
    cl = col.lower().strip()
    if 'station' in cl and 'id' in cl:
        station_col = col
    elif cl == 'station':
        station_col = col
    elif 'temp' in cl and 'mean' not in cl.replace('temperature', ''):
        temp_col = col
    elif 'temp' in cl:
        temp_col = col

if station_col is None:
    for col in data.columns:
        if 'station' in col.lower():
            station_col = col
            break

if temp_col is None:
    for col in data.columns:
        if 'temp' in col.lower():
            temp_col = col
            break

print(f"Using station_col={station_col}, temp_col={temp_col}")

# Calculate mean temperature per station
means = data.groupby(station_col)[temp_col].mean()

for station_id, mean_temp in means.items():
    print(f"Station {station_id}: Mean Temperature = {mean_temp:.1f} C")

print("\nAnalysis complete.")
PYEOF

python3 /app/analyze_climate_modern.py
