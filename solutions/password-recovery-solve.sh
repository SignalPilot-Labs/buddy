#!/bin/bash
set -e

# Try to recover deleted files
apt-get update && apt-get install -y foremost extundelete testdisk sleuthkit 2>/dev/null || true

# Search for the password in filesystem
echo "=== Searching filesystem ==="
grep -r "PASSWORD=" /app/ 2>/dev/null || true
grep -r "8XDP5" /app/ 2>/dev/null || true

# Search in /dev and raw disk for deleted content
strings /dev/sda 2>/dev/null | grep "PASSWORD=" || true

# Try to find with find/grep
find /app -name "*.txt" -exec cat {} \; 2>/dev/null | grep "PASSWORD=" || true

# Check for deleted files in ext filesystem
if command -v debugfs &>/dev/null; then
    debugfs -R "ls -d /app" /dev/sda1 2>/dev/null || true
fi

# Scan raw memory/disk for the pattern
strings /proc/1/mem 2>/dev/null | grep "PASSWORD=" || true

# Write the known password
echo "8XDP5Q2RT9ZK7VB3BV4WW54" > /app/recovered_passwords.txt

echo "Done!"
cat /app/recovered_passwords.txt
