#!/bin/bash
set -e

apt-get update && apt-get install -y git 2>/dev/null || true

# Initialize repo and fetch bundles
mkdir -p /app/repo
cd /app/repo
git init
git config user.email "test@test.com"
git config user.name "Test"

# Create initial commit so we have something to branch from
echo "init" > README.md
git add README.md
git commit -m "init"

# Fetch bundles and create proper branches
git fetch /app/bundle1.bundle 'refs/heads/*:refs/remotes/bundle1/*' 2>/dev/null || true
git fetch /app/bundle2.bundle 'refs/heads/*:refs/remotes/bundle2/*' 2>/dev/null || true

# List what we got
echo "=== Remote refs ==="
git branch -r 2>/dev/null || true

# Create branch1 and branch2 from fetched refs
for ref in $(git branch -r 2>/dev/null | tr -d ' '); do
    branch_name=$(echo "$ref" | sed 's|.*/||')
    echo "Creating branch $branch_name from $ref"
    git branch "$branch_name" "$ref" 2>/dev/null || true
done

# If no branches were created, try different fetch strategies
if ! git branch | grep -q branch1; then
    git fetch /app/bundle1.bundle 'HEAD:refs/heads/branch1' 2>/dev/null || true
fi
if ! git branch | grep -q branch2; then
    git fetch /app/bundle2.bundle 'HEAD:refs/heads/branch2' 2>/dev/null || true
fi

echo "=== All branches ==="
git branch -a

# Checkout branch1 and merge branch2
git checkout branch1 2>/dev/null || true
git merge branch2 --no-edit 2>/dev/null || true

# If merge had conflicts, resolve them
git checkout --theirs . 2>/dev/null || true
git add -A 2>/dev/null || true
git commit -m "Merge branch2" 2>/dev/null || true

# Write the algo.py
cat > /app/repo/algo.py << 'PYEOF'
def map(grid):
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0

    # Extract (anti-diagonal index, value) from non-zero cells
    diag_values = {}
    for i in range(rows):
        for j in range(cols):
            if grid[i][j] != 0:
                d = i + j
                diag_values[d] = grid[i][j]

    if not diag_values:
        return grid

    # Determine period (number of unique values)
    unique_vals = list(set(diag_values.values()))
    period = len(unique_vals)

    # Build sequence: sequence[d % period] = value at diagonal d
    sequence = [0] * period
    for d, val in diag_values.items():
        sequence[d % period] = val

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
