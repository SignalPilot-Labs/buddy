#!/bin/bash
set -e

cat > /app/recover.py << 'PYEOF'
import sqlite3
import json
import os
import struct

# Find database and WAL files
db_path = None
wal_path = None

for f in os.listdir("/app"):
    full = os.path.join("/app", f)
    if f.endswith(".db") or f.endswith(".sqlite") or f.endswith(".sqlite3"):
        db_path = full
    if f.endswith("-wal"):
        wal_path = full

print(f"DB: {db_path}, WAL: {wal_path}")

# If WAL exists, try to decrypt it
if wal_path and os.path.exists(wal_path):
    with open(wal_path, 'rb') as f:
        wal_data = f.read()

    print(f"WAL size: {len(wal_data)}, first 4 bytes: {wal_data[:4].hex()}")

    # Try XOR decryption with all single-byte keys
    for key in range(256):
        first4 = bytes(b ^ key for b in wal_data[:4])
        magic = struct.unpack('>I', first4)[0]
        if magic in (0x377f0682, 0x377f0683):
            print(f"Found XOR key: 0x{key:02x}")
            decrypted = bytes(b ^ key for b in wal_data)
            with open(wal_path, 'wb') as f:
                f.write(decrypted)
            print("WAL decrypted and replaced")
            break

# Now read the database (SQLite will auto-apply WAL)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

data = []
for table_name, in tables:
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY id")
    rows = cursor.fetchall()
    cols = [d[0] for d in cursor.description]
    for row in rows:
        data.append(dict(zip(cols, row)))

conn.close()

data.sort(key=lambda x: x["id"])

with open("/app/recovered.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"Recovered {len(data)} records")
for r in data:
    print(f"  {r}")
PYEOF

python3 /app/recover.py
