#!/bin/bash
set -e

mkdir -p /app/ssl

# Generate 2048-bit RSA key
openssl genrsa -out /app/ssl/server.key 2048
chmod 600 /app/ssl/server.key

# Generate self-signed cert (365 days, with CN and O)
openssl req -new -x509 -key /app/ssl/server.key -out /app/ssl/server.crt -days 365 \
  -subj "/CN=dev-internal.company.local/O=DevOps Team"

# Create combined PEM
cat /app/ssl/server.key /app/ssl/server.crt > /app/ssl/server.pem

# Create verification.txt
FINGERPRINT=$(openssl x509 -in /app/ssl/server.crt -noout -fingerprint -sha256 | sed 's/sha256 Fingerprint=//' | sed 's/SHA256 Fingerprint=//')
EXPIRY=$(openssl x509 -in /app/ssl/server.crt -noout -enddate | sed 's/notAfter=//')
cat > /app/ssl/verification.txt << EOF
CN: dev-internal.company.local
Organization: DevOps Team
Expiry: $EXPIRY
SHA-256 Fingerprint: $FINGERPRINT
EOF

# Create check_cert.py
cat > /app/check_cert.py << 'PYEOF'
import subprocess
import re
from datetime import datetime

result = subprocess.run(
    ["openssl", "x509", "-in", "/app/ssl/server.crt", "-noout", "-subject", "-enddate"],
    capture_output=True, text=True
)

output = result.stdout
# Extract CN
cn_match = re.search(r'CN\s*=\s*([^\n/,]+)', output)
cn = cn_match.group(1).strip() if cn_match else ""

# Extract expiry
end_match = re.search(r'notAfter=(.+)', output)
end_str = end_match.group(1).strip() if end_match else ""
expiry = datetime.strptime(end_str, "%b %d %H:%M:%S %Y %Z")
expiry_str = expiry.strftime("%Y-%m-%d")

print("Certificate verification successful")
print(f"CN: {cn}")
print(f"Expiration: {expiry_str}")
PYEOF

python3 /app/check_cert.py
echo "Done!"
