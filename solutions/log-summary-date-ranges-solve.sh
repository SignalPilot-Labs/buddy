#!/bin/bash
set -e

cat > /app/summarize.py << 'PYEOF'
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

REF_DATE = datetime(2025, 8, 12).date()

# Date ranges
today = REF_DATE
last_7_start = REF_DATE - timedelta(days=6)
last_30_start = REF_DATE - timedelta(days=29)
month_start = REF_DATE.replace(day=1)

def get_periods(date):
    periods = ["total"]
    if date == today:
        periods.append("today")
    if last_7_start <= date <= today:
        periods.append("last_7_days")
    if last_30_start <= date <= today:
        periods.append("last_30_days")
    if month_start <= date <= today:
        periods.append("month_to_date")
    return periods

# Count by period and severity
counts = defaultdict(lambda: defaultdict(int))

log_dir = Path("/app/logs")
# Log line format: YYYY-MM-DD HH:MM:SS [SEVERITY] message
severity_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[(ERROR|WARNING|INFO|DEBUG)\] ')

for log_file in sorted(log_dir.glob("*.log")):
    # Extract date from filename: YYYY-MM-DD_source.log
    fname = log_file.name
    file_date_str = fname[:10]
    try:
        file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
    except ValueError:
        continue

    periods = get_periods(file_date)
    if not periods:
        continue

    with open(log_file) as f:
        for line in f:
            m = severity_pattern.match(line)
            if m:
                severity = m.group(1)
                if severity == "DEBUG":
                    continue
                for period in periods:
                    counts[period][severity] += 1

# Write CSV in exact order
period_order = ["today", "last_7_days", "last_30_days", "month_to_date", "total"]
severity_order = ["ERROR", "WARNING", "INFO"]

with open("/app/summary.csv", "w") as f:
    f.write("period,severity,count\n")
    for period in period_order:
        for severity in severity_order:
            count = counts[period][severity]
            f.write(f"{period},{severity},{count}\n")

print("Summary written to /app/summary.csv")
with open("/app/summary.csv") as f:
    print(f.read())
PYEOF

python3 /app/summarize.py
