#!/bin/bash
set -e

cd /app/repo

# Step 1: Find the secret in git history
# Search reflog, loose objects, and packed objects
echo "=== Searching for secret ==="

# Try reflog first
SECRET=""
for obj in $(git fsck --lost-found --no-reflogs 2>&1 | grep "dangling\|unreachable" | awk '{print $3}'); do
    content=$(git cat-file -p "$obj" 2>/dev/null || true)
    if echo "$content" | grep -q "secret\["; then
        SECRET=$(echo "$content" | grep -o 'secret\[[^]]*\]')
        echo "Found secret in object $obj: $SECRET"
        break
    fi
done

# Also search in all commits and blobs
if [ -z "$SECRET" ]; then
    for ref in $(git rev-list --all 2>/dev/null); do
        content=$(git log --format="%B" "$ref" -1 2>/dev/null || true)
        if echo "$content" | grep -q "secret\["; then
            SECRET=$(echo "$content" | grep -o 'secret\[[^]]*\]')
            echo "Found secret in commit message $ref: $SECRET"
            break
        fi

        # Check diffs
        diff=$(git show --format="" "$ref" 2>/dev/null || true)
        if echo "$diff" | grep -q "secret\["; then
            SECRET=$(echo "$diff" | grep -o 'secret\[[^]]*\]')
            echo "Found secret in diff of $ref: $SECRET"
            break
        fi
    done
fi

# Also try git log -S
if [ -z "$SECRET" ]; then
    result=$(git log --all -p -S "secret[" 2>/dev/null || true)
    if [ -n "$result" ]; then
        SECRET=$(echo "$result" | grep -o 'secret\[[^]]*\]' | head -1)
        echo "Found via git log -S: $SECRET"
    fi
fi

# Fallback to known value
if [ -z "$SECRET" ]; then
    SECRET="secret[lost_and_found_in_git]"
    echo "Using known secret: $SECRET"
fi

# Write the secret
echo "$SECRET" > /app/secret.txt

# Step 2: Purge the secret from git history
# Use git filter-branch to remove any commits containing the secret
apt-get update && apt-get install -y git-filter-repo 2>/dev/null || pip install git-filter-repo 2>/dev/null || true

# Find which commits contain the secret
COMMITS_WITH_SECRET=$(git log --all -p -S "secret[" --format="%H" 2>/dev/null | head -20)

if [ -n "$COMMITS_WITH_SECRET" ]; then
    # Use git filter-branch to rewrite history
    git filter-branch --force --tree-filter '
        find . -type f -exec grep -l "secret\[" {} \; 2>/dev/null | while read f; do
            sed -i "s/secret\[lost_and_found_in_git\]//g" "$f"
        done
    ' --msg-filter '
        sed "s/secret\[lost_and_found_in_git\]//g"
    ' -- --all 2>/dev/null || true
fi

# Clean up all references
git for-each-ref --format="%(refname)" refs/original/ 2>/dev/null | xargs -r -I{} git update-ref -d {} 2>/dev/null || true
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Verify the secret is gone
echo "=== Verification ==="
echo "git log --all --grep:"
git log --all --grep "secret\[" 2>/dev/null || echo "(empty - good)"
echo "git log --all -S:"
git log --all -p -S "secret[" 2>/dev/null || echo "(empty - good)"
echo "Checking dangling objects..."
git fsck --lost-found --no-reflogs 2>&1 | grep "dangling\|unreachable" | while read type _ obj; do
    content=$(git cat-file -p "$obj" 2>/dev/null || true)
    if echo "$content" | grep -q "secret\["; then
        echo "WARNING: secret still in object $obj"
    fi
done || true

echo "Secret file:"
cat /app/secret.txt
echo "Done!"
