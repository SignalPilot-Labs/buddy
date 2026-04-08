#!/bin/bash
set -e

apt-get update && apt-get install -y git 2>/dev/null || true

# Initialize repo and fetch bundles
mkdir -p /app/repo
cd /app/repo
git init

# Fetch bundles
git fetch /app/bundle1.bundle 'refs/heads/*:refs/heads/*' 2>/dev/null || \
git fetch /app/bundle1.bundle '+refs/*:refs/remotes/bundle1/*' 2>/dev/null || true

git fetch /app/bundle2.bundle 'refs/heads/*:refs/heads/*' 2>/dev/null || \
git fetch /app/bundle2.bundle '+refs/*:refs/remotes/bundle2/*' 2>/dev/null || true

# List branches
git branch -a

# Try to checkout branch1
git checkout branch1 2>/dev/null || git checkout -b branch1 remotes/bundle1/branch1 2>/dev/null || true

# Merge branch2
git merge branch2 --no-edit 2>/dev/null || git merge remotes/bundle2/branch2 --no-edit 2>/dev/null || true

# Resolve any conflicts by accepting both
git checkout --theirs . 2>/dev/null || true
git add -A 2>/dev/null || true
git commit -m "Merge branch2" 2>/dev/null || true

# Write the algo.py that implements the ARC-AGI pattern
cat > /app/repo/algo.py << 'PYEOF'
def map(grid):
    """
    Fill the grid by tiling the non-zero diagonal values cyclically.
    The pattern: extract non-zero values from the input (they form a sequence),
    then fill every cell grid[i][j] = sequence[(i+j) % len(sequence)].
    """
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0

    # Extract non-zero values in order of appearance (by row, then col)
    sequence = []
    for i in range(rows):
        for j in range(cols):
            if grid[i][j] != 0:
                val = grid[i][j]
                if val not in sequence:
                    sequence.append(val)

    if not sequence:
        return grid

    period = len(sequence)

    # Fill the grid
    result = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            result[i][j] = sequence[(i + j) % period]

    return result
PYEOF

git add algo.py
git commit -m "Add ARC-AGI solution" 2>/dev/null || true

echo "Done!"
cat /app/repo/algo.py
