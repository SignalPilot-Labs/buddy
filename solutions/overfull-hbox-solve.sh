#!/bin/bash
set -e

# Parse overfull hbox warnings from pdflatex log and substitute synonyms to fix them.
# The script:
#   1. Compiles main.tex with pdflatex
#   2. Parses main.log for overfull hbox warnings
#   3. For each overfull line, tries synonym substitutions to shorten the line
#   4. Repeats until no overfull hboxes remain

export DEBIAN_FRONTEND=noninteractive

# Install python3 if not available
if ! command -v python3 &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq python3
fi

cd /app

# Write the Python fixer script
cat > /tmp/fix_overfull.py << 'PYEOF'
import re
import subprocess
import sys


def parse_log_overfull(log_path: str) -> list[tuple[int, str]]:
    """Return list of (line_number, content_snippet) for each overfull hbox warning."""
    results: list[tuple[int, str]] = []
    with open(log_path, "r", errors="replace") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        if "Overfull \\hbox" in line:
            # Extract line number: pattern "lines N--M" or "line N"
            m = re.search(r"lines?\s+(\d+)", line)
            line_num = int(m.group(1)) if m else 0
            # Next line contains the typeset content (strip leading spaces and hyphens)
            snippet = ""
            if i + 1 < len(lines):
                snippet = lines[i + 1].strip().lstrip("-").strip()
            results.append((line_num, snippet))
        i += 1
    return results


def build_synonym_map(syn_path: str) -> dict[str, set[str]]:
    """Return dict mapping each word to its full synonym family."""
    synonyms: dict[str, set[str]] = {}
    with open(syn_path, "r") as f:
        for line in f:
            words = set(line.strip().split(", "))
            for word in words:
                synonyms[word] = words
    return synonyms


def word_length(word: str) -> int:
    return len(word)


def try_fix_line(
    tex_lines: list[str],
    line_idx: int,
    synonyms: dict[str, set[str]],
) -> tuple[list[str], bool]:
    """
    Try to substitute a word on the given 0-indexed line with a shorter synonym.
    Returns (new_lines, changed).
    """
    original = tex_lines[line_idx]
    tokens = re.findall(r"[A-Za-z]+", original)

    best_lines: list[str] | None = None
    best_savings = 0

    for token in tokens:
        if token not in synonyms:
            continue
        family = synonyms[token]
        shorter_alternatives = [
            alt for alt in family
            if alt != token and word_length(alt) < word_length(token)
        ]
        if not shorter_alternatives:
            continue
        # Pick the shortest alternative
        best_alt = min(shorter_alternatives, key=word_length)
        savings = word_length(token) - word_length(best_alt)
        if savings > best_savings:
            # Replace first occurrence on this line (preserving case context via exact match)
            new_line = re.sub(r"\b" + re.escape(token) + r"\b", best_alt, original, count=1)
            if new_line != original:
                new_lines = tex_lines[:]
                new_lines[line_idx] = new_line
                best_lines = new_lines
                best_savings = savings

    if best_lines is not None:
        return best_lines, True
    return tex_lines, False


def try_fix_with_any_synonym(
    tex_lines: list[str],
    line_idx: int,
    synonyms: dict[str, set[str]],
) -> tuple[list[str], bool]:
    """
    Try any synonym substitution (not just shorter) to give pdflatex more flexibility.
    Tries all tokens and all alternatives, returns first one that differs.
    """
    original = tex_lines[line_idx]
    tokens = re.findall(r"[A-Za-z]+", original)

    for token in tokens:
        if token not in synonyms:
            continue
        family = synonyms[token]
        alternatives = [alt for alt in family if alt != token]
        if not alternatives:
            continue
        # Prefer shortest alternative
        best_alt = min(alternatives, key=word_length)
        new_line = re.sub(r"\b" + re.escape(token) + r"\b", best_alt, original, count=1)
        if new_line != original:
            new_lines = tex_lines[:]
            new_lines[line_idx] = new_line
            return new_lines, True

    return tex_lines, False


def fix_one_overfull(
    tex_path: str,
    log_path: str,
    syn_path: str,
) -> bool:
    """
    Parse the log, find one overfull hbox, apply a synonym substitution.
    Returns True if a substitution was made.
    """
    overfull = parse_log_overfull(log_path)
    if not overfull:
        return False

    synonyms = build_synonym_map(syn_path)

    with open(tex_path, "r") as f:
        tex_lines = f.readlines()

    for line_num, snippet in overfull:
        if line_num <= 0 or line_num > len(tex_lines):
            continue

        line_idx = line_num - 1
        new_lines, changed = try_fix_line(tex_lines, line_idx, synonyms)

        if not changed:
            # Try using any synonym (not just shorter ones) for flexibility
            new_lines, changed = try_fix_with_any_synonym(tex_lines, line_idx, synonyms)

        if changed:
            with open(tex_path, "w") as f:
                f.writelines(new_lines)
            return True

        # Try searching surrounding lines (pdflatex line numbers can be approximate)
        for offset in [-1, 1, -2, 2]:
            alt_idx = line_idx + offset
            if 0 <= alt_idx < len(tex_lines):
                new_lines, changed = try_fix_line(tex_lines, alt_idx, synonyms)
                if not changed:
                    new_lines, changed = try_fix_with_any_synonym(tex_lines, alt_idx, synonyms)
                if changed:
                    with open(tex_path, "w") as f:
                        f.writelines(new_lines)
                    return True

    return False


if __name__ == "__main__":
    tex_path = sys.argv[1] if len(sys.argv) > 1 else "input.tex"
    log_path = sys.argv[2] if len(sys.argv) > 2 else "main.log"
    syn_path = sys.argv[3] if len(sys.argv) > 3 else "synonyms.txt"

    made_change = fix_one_overfull(tex_path, log_path, syn_path)
    if made_change:
        print("Applied synonym substitution.")
        sys.exit(0)
    else:
        print("No substitution found for remaining overfull hboxes.", file=sys.stderr)
        sys.exit(1)
PYEOF

# Initial compile
pdflatex -interaction=nonstopmode main.tex || true

MAX_ITERATIONS=100
iteration=0

while grep -q "Overfull" main.log; do
    iteration=$((iteration + 1))
    if [ "$iteration" -gt "$MAX_ITERATIONS" ]; then
        echo "ERROR: Reached max iterations ($MAX_ITERATIONS) without eliminating all overfull hboxes."
        exit 1
    fi

    echo "Iteration $iteration: fixing overfull hbox..."
    if ! python3 /tmp/fix_overfull.py /app/input.tex /app/main.log /app/synonyms.txt; then
        echo "ERROR: Could not find a valid synonym substitution for remaining overfull hboxes."
        exit 1
    fi

    pdflatex -interaction=nonstopmode main.tex || true
done

echo "All overfull hboxes resolved after $iteration iteration(s)."
