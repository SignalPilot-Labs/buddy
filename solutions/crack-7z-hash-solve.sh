#!/bin/bash
set -e

# Install python and 7zip
apt-get update -qq
apt-get install -y -qq python3 python3-pip p7zip-full 2>/dev/null || true
pip install py7zr 2>/dev/null || pip3 install py7zr 2>/dev/null || true

# Try to crack with py7zr using john's wordlist
python3 << 'PYEOF'
import sys
import os

# Try py7zr first
try:
    import py7zr

    def try_password(pw):
        try:
            with py7zr.SevenZipFile('/app/secrets.7z', password=pw) as z:
                z.extractall('/app/extracted')
            return True
        except Exception:
            return False

    # Try john's password list
    wordlist = '/app/john/run/password.lst'
    if os.path.exists(wordlist):
        with open(wordlist, 'r', errors='ignore') as f:
            for line in f:
                pw = line.strip()
                if not pw or pw.startswith('#'):
                    continue
                if try_password(pw):
                    print(f'Found password: {pw}')
                    # Write solution
                    secret_path = None
                    for root, dirs, files in os.walk('/app/extracted'):
                        for fname in files:
                            if 'secret' in fname.lower():
                                secret_path = os.path.join(root, fname)
                    if secret_path:
                        with open(secret_path) as sf:
                            content = sf.read()
                        with open('/app/solution.txt', 'w') as out:
                            out.write(content)
                        print(f'Solution written: {content[:100]}')
                    sys.exit(0)

    print('Password not found in wordlist')
    sys.exit(1)

except ImportError:
    # Fallback: use 7z command line with wordlist
    import subprocess
    wordlist = '/app/john/run/password.lst'
    with open(wordlist, 'r', errors='ignore') as f:
        for line in f:
            pw = line.strip()
            if not pw or pw.startswith('#'):
                continue
            result = subprocess.run(
                ['7z', 'x', f'-p{pw}', '/app/secrets.7z', '-o/app/extracted', '-y'],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f'Found password: {pw}')
                # Find and write solution
                for root, dirs, files in os.walk('/app/extracted'):
                    for fname in files:
                        if 'secret' in fname.lower():
                            with open(os.path.join(root, fname)) as sf:
                                content = sf.read()
                            with open('/app/solution.txt', 'w') as out:
                                out.write(content)
                            print(f'Solution: {content[:100]}')
                sys.exit(0)

    print('Password not found')
    sys.exit(1)
PYEOF

echo "Solution:"
cat /app/solution.txt
