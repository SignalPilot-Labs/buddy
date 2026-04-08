#!/bin/bash
set -e

pip install pypiserver build setuptools wheel

# Create package structure
mkdir -p /app/vectorops-pkg/vectorops
cat > /app/vectorops-pkg/vectorops/__init__.py << 'EOF'
def dotproduct(a, b):
    return sum(x * y for x, y in zip(a, b))
EOF

cat > /app/vectorops-pkg/setup.py << 'EOF'
from setuptools import setup, find_packages

setup(
    name="vectorops",
    version="0.1.0",
    packages=find_packages(),
)
EOF

cat > /app/vectorops-pkg/pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"
EOF

# Build the package
cd /app/vectorops-pkg
python3 -m build 2>&1 || python3 setup.py sdist bdist_wheel 2>&1

# Create packages directory for pypiserver
mkdir -p /app/packages
cp dist/* /app/packages/

echo "=== Built packages ==="
ls -la /app/packages/

# Start PyPI server on port 8080
nohup pypi-server run -p 8080 /app/packages > /tmp/pypi.log 2>&1 &
sleep 2

# Verify server is running
curl -s http://localhost:8080/ | head -5

# Test install
pip install --index-url http://localhost:8080/simple/ vectorops==0.1.0
python3 -c "from vectorops import dotproduct; print(dotproduct([1,1], [0,1]))"

echo "Done!"
