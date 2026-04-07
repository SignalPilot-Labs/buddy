#!/bin/bash
# Solution for git-leak-recovery challenge
# 1. Find the secret in dangling git objects
# 2. Write it to /app/secret.txt
# 3. Scrub all traces from git history

cd /app/repo

# Step 1: Find secret in reflog
SECRET=$(git show $(git reflog --format='%H' | while read h; do
    git show "$h:secret.txt" 2>/dev/null && break
done | head -1))
# Simplified: we know the secret commit is in reflog
SECRET=$(git show HEAD@{2}:secret.txt 2>/dev/null || \
         git log --all --diff-filter=D --name-only --format="" | \
         xargs -I{} git log --all -p -- {} | grep 'secret\[')

# Direct approach - find the dangling commit
SECRET=$(git fsck --lost-found 2>/dev/null | grep commit | awk '{print $3}' | \
         while read h; do git show "$h:secret.txt" 2>/dev/null; done)

# Fallback: search reflog directly
if [ -z "$SECRET" ]; then
    SECRET=$(git reflog --format='%H' | while read h; do
        git show "$h:secret.txt" 2>/dev/null && break
    done)
fi

# Step 2: Write secret
echo "$SECRET" > /app/secret.txt

# Step 3: Scrub git history
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo "Done. Secret: $(cat /app/secret.txt)"
