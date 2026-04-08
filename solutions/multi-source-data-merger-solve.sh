#!/bin/bash
set -e

pip install pandas pyarrow

cat > /app/merge.py << 'PYEOF'
import json
import pandas as pd
import os
import glob

# Find data directories
data_dirs = ["/data", "/app/data", "/app"]
data_base = None
for d in data_dirs:
    if os.path.exists(os.path.join(d, "source_a")):
        data_base = d
        break

if data_base is None:
    # Search more broadly
    for root, dirs, files in os.walk("/"):
        if "source_a" in dirs:
            data_base = root
            break

print(f"Data base: {data_base}")

# Read source_a (JSON)
sa_path = glob.glob(f"{data_base}/source_a/*.json")[0]
with open(sa_path) as f:
    sa_data = json.load(f)
if isinstance(sa_data, dict) and "users" in sa_data:
    sa_data = sa_data["users"]
df_a = pd.DataFrame(sa_data)
print(f"Source A columns: {list(df_a.columns)}")

# Read source_b (CSV)
sb_path = glob.glob(f"{data_base}/source_b/*.csv")[0]
df_b = pd.read_csv(sb_path)
print(f"Source B columns: {list(df_b.columns)}")

# Read source_c (Parquet)
sc_path = glob.glob(f"{data_base}/source_c/*.parquet")[0]
df_c = pd.read_parquet(sc_path)
print(f"Source C columns: {list(df_c.columns)}")

# Field name mapping
FIELD_MAP = {
    "id": "user_id",
    "userId": "user_id",
    "user_id": "user_id",
    "full_name": "name",
    "userName": "name",
    "name": "name",
    "email_address": "email",
    "email": "email",
    "registration_date": "created_date",
    "created_at": "created_date",
    "joined": "created_date",
    "created_date": "created_date",
    "status": "status",
}

def normalize_df(df, source_name):
    renamed = {}
    for col in df.columns:
        if col in FIELD_MAP:
            renamed[col] = FIELD_MAP[col]
    df = df.rename(columns=renamed)
    df["_source"] = source_name
    # Ensure user_id is int
    if "user_id" in df.columns:
        df["user_id"] = df["user_id"].astype(int)
    # Ensure created_date is string YYYY-MM-DD
    if "created_date" in df.columns:
        df["created_date"] = pd.to_datetime(df["created_date"]).dt.strftime("%Y-%m-%d")
    return df

df_a = normalize_df(df_a, "source_a")
df_b = normalize_df(df_b, "source_b")
df_c = normalize_df(df_c, "source_c")

# Standard columns
std_cols = ["user_id", "name", "email", "created_date", "status"]

for col in std_cols:
    for df in [df_a, df_b, df_c]:
        if col not in df.columns:
            df[col] = None

# Get all unique user_ids
all_ids = sorted(set(df_a["user_id"].tolist() + df_b["user_id"].tolist() + df_c["user_id"].tolist()))

# Priority merge: a > b > c
sources = [("source_a", df_a), ("source_b", df_b), ("source_c", df_c)]
merge_fields = ["name", "email", "created_date", "status"]

merged_rows = []
conflicts_list = []

for uid in all_ids:
    row = {"user_id": uid}

    # Get data from each source for this user
    source_data = {}
    for sname, sdf in sources:
        match = sdf[sdf["user_id"] == uid]
        if len(match) > 0:
            source_data[sname] = match.iloc[0].to_dict()

    # For each field, pick highest priority value and detect conflicts
    for field in merge_fields:
        values = {}
        for sname in ["source_a", "source_b", "source_c"]:
            if sname in source_data:
                val = source_data[sname].get(field)
                if val is not None and str(val) != "nan" and str(val) != "None":
                    values[sname] = val

        # Pick highest priority
        selected = None
        selected_source = None
        for sname in ["source_a", "source_b", "source_c"]:
            if sname in values:
                selected = values[sname]
                selected_source = sname
                break

        row[field] = selected

        # Detect conflicts (different values across sources)
        unique_vals = set(str(v) for v in values.values())
        if len(unique_vals) > 1:
            conflict = {
                "user_id": int(uid),
                "field": field,
                "values": {k: str(v) for k, v in values.items()},
                "selected": str(selected),
                "selected_source": selected_source,
            }
            conflicts_list.append(conflict)

    merged_rows.append(row)

# Create merged DataFrame
merged_df = pd.DataFrame(merged_rows)
merged_df["user_id"] = merged_df["user_id"].astype(int)

# Write parquet
merged_df[["user_id", "name", "email", "created_date", "status"]].to_parquet(
    "/app/merged_users.parquet", index=False
)

# Write conflicts
conflicts_output = {
    "total_conflicts": len(conflicts_list),
    "conflicts": conflicts_list,
}
with open("/app/conflicts.json", "w") as f:
    json.dump(conflicts_output, f, indent=2)

print(f"Merged {len(merged_rows)} users")
print(f"Found {len(conflicts_list)} conflicts")
print(merged_df.to_string())
PYEOF

python3 /app/merge.py
