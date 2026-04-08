#!/bin/bash
set -e

# Create the pyproject.toml for the uv venv in /app
# Use setuptools with no packages — this is a scripts-only project.
# hatchling fails when there are no Python packages to discover.
cat > /app/pyproject.toml << 'EOF'
[project]
name = "reshard-c4"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = []
EOF

# Create compress.py
cat > /app/compress.py << 'COMPRESS_EOF'
"""
Reshard JSONL files into a tree structure.

Constraints:
- Max 30 items (files + subdirs) per directory
- Max 15MB per output file

Strategy:
- Split large files into chunks <= 15MB
- Organize chunks into a balanced tree (base-BRANCH) where each dir <= 30 items
- The root also holds manifest.json, so root uses BRANCH = MAX_ITEMS - 1 = 29 slots
  for data; inner/leaf dirs use MAX_ITEMS = 30 slots.
- manifest.json at root stores how to reconstruct each original file from chunks.
"""
import json
import math
import os
import sys

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15MB in bytes
MAX_ITEMS_PER_DIR = 30
# Root dir reserves one slot for manifest.json
ROOT_BRANCH = MAX_ITEMS_PER_DIR - 1  # 29
INNER_BRANCH = MAX_ITEMS_PER_DIR     # 30
MANIFEST_FILENAME = "manifest.json"


def collect_chunks(input_dir: str) -> list[dict]:
    """
    Read all input JSONL files and split into chunks <= MAX_FILE_SIZE.
    Returns list of dicts: {original_filename, chunk_index, lines}
    """
    chunks: list[dict] = []
    input_files = sorted(os.listdir(input_dir))

    for fname in input_files:
        fpath = os.path.join(input_dir, fname)
        if not os.path.isfile(fpath):
            continue

        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_lines: list[str] = []
        current_size = 0
        chunk_index = 0

        for line in lines:
            line_bytes = len(line.encode("utf-8"))
            if current_lines and current_size + line_bytes > MAX_FILE_SIZE:
                chunks.append({
                    "original_filename": fname,
                    "chunk_index": chunk_index,
                    "lines": current_lines,
                })
                chunk_index += 1
                current_lines = []
                current_size = 0
            current_lines.append(line)
            current_size += line_bytes

        if current_lines:
            chunks.append({
                "original_filename": fname,
                "chunk_index": chunk_index,
                "lines": current_lines,
            })

    return chunks


def compute_depth(num_chunks: int) -> int:
    """
    Compute minimum tree depth needed to hold num_chunks leaf files.

    Root has ROOT_BRANCH slots for data; all other dirs have INNER_BRANCH slots.
    Depth 1: root holds up to ROOT_BRANCH files directly.
    Depth 2: root has up to ROOT_BRANCH subdirs, each with up to INNER_BRANCH files.
    Depth d: root * INNER_BRANCH^(d-1) capacity.
    """
    if num_chunks <= ROOT_BRANCH:
        return 1
    depth = 1
    capacity = ROOT_BRANCH
    while capacity < num_chunks:
        depth += 1
        capacity = ROOT_BRANCH * (INNER_BRANCH ** (depth - 1))
    return depth


def chunk_index_to_path_parts(index: int, depth: int) -> list[str]:
    """
    Convert a flat chunk index to directory/file name parts.

    Layout for depth d:
      - Most-significant digit: root-level index (0..ROOT_BRANCH-1)
      - Remaining digits: inner-level indices (0..INNER_BRANCH-1)
    """
    if depth == 1:
        return [str(index)]

    parts: list[int] = []
    remaining = index

    # Leaf and inner digits (right to left), all base INNER_BRANCH
    for _ in range(depth - 1):
        parts.append(remaining % INNER_BRANCH)
        remaining //= INNER_BRANCH

    # Root digit, base ROOT_BRANCH
    parts.append(remaining % ROOT_BRANCH)
    parts.reverse()

    return [str(p) for p in parts]


def write_chunks(chunks: list[dict], output_dir: str) -> list[dict]:
    """
    Write chunks into a tree under output_dir.
    Returns manifest entries: [{output_path, original_filename, chunk_index}]
    """
    depth = compute_depth(len(chunks))
    manifest_entries: list[dict] = []

    for i, chunk in enumerate(chunks):
        path_parts = chunk_index_to_path_parts(i, depth)

        # All parts except the last are subdirectories; last is the file leaf
        dir_parts = path_parts[:-1]
        file_leaf = path_parts[-1]

        chunk_dir = output_dir
        for part in dir_parts:
            chunk_dir = os.path.join(chunk_dir, part)

        os.makedirs(chunk_dir, exist_ok=True)

        chunk_filename = f"{file_leaf}.jsonl"
        chunk_path = os.path.join(chunk_dir, chunk_filename)

        with open(chunk_path, "w", encoding="utf-8") as f:
            f.writelines(chunk["lines"])

        rel_path = os.path.relpath(chunk_path, output_dir)
        manifest_entries.append({
            "output_path": rel_path,
            "original_filename": chunk["original_filename"],
            "chunk_index": chunk["chunk_index"],
        })

    return manifest_entries


def write_manifest(manifest_entries: list[dict], output_dir: str) -> None:
    """Write manifest.json to the root of output_dir."""
    manifest_path = os.path.join(output_dir, MANIFEST_FILENAME)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_entries, f)


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_dir> <output_dir>", file=sys.stderr)
        sys.exit(1)

    input_dir = sys.argv[1]
    output_dir = sys.argv[2]

    os.makedirs(output_dir, exist_ok=True)

    print(f"Collecting and splitting chunks from {input_dir}...")
    chunks = collect_chunks(input_dir)
    print(f"Total chunks to write: {len(chunks)}")

    print(f"Writing chunks to tree under {output_dir}...")
    manifest_entries = write_chunks(chunks, output_dir)

    print("Writing manifest...")
    write_manifest(manifest_entries, output_dir)

    print(f"Done. {len(manifest_entries)} chunk(s) written.")


if __name__ == "__main__":
    main()
COMPRESS_EOF

# Create decompress.py
cat > /app/decompress.py << 'DECOMPRESS_EOF'
"""
Reconstruct original JSONL files from a resharded directory.

Reads manifest.json at the root, reassembles originals by concatenating
ordered chunks, then replaces the tree with flat original files in-place.
"""
import json
import os
import shutil
import sys
import tempfile

MANIFEST_FILENAME = "manifest.json"


def load_manifest(resharded_dir: str) -> list[dict]:
    """Load and return the manifest from the resharded directory."""
    manifest_path = os.path.join(resharded_dir, MANIFEST_FILENAME)
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def group_by_original(manifest_entries: list[dict]) -> dict[str, list[dict]]:
    """Group manifest entries by original filename, sorted by chunk_index."""
    groups: dict[str, list[dict]] = {}
    for entry in manifest_entries:
        fname = entry["original_filename"]
        if fname not in groups:
            groups[fname] = []
        groups[fname].append(entry)

    for fname in groups:
        groups[fname].sort(key=lambda e: e["chunk_index"])

    return groups


def reconstruct_files(
    groups: dict[str, list[dict]],
    resharded_dir: str,
    staging_dir: str,
) -> None:
    """Write reconstructed original files to staging_dir."""
    for original_filename, chunks in groups.items():
        out_path = os.path.join(staging_dir, original_filename)
        with open(out_path, "w", encoding="utf-8") as out_f:
            for chunk_entry in chunks:
                chunk_path = os.path.join(resharded_dir, chunk_entry["output_path"])
                with open(chunk_path, "r", encoding="utf-8") as in_f:
                    out_f.write(in_f.read())


def replace_tree_with_originals(resharded_dir: str, staging_dir: str) -> None:
    """
    Remove all contents of resharded_dir, then move reconstructed files in.
    """
    for item in os.listdir(resharded_dir):
        item_path = os.path.join(resharded_dir, item)
        if os.path.isdir(item_path):
            shutil.rmtree(item_path)
        else:
            os.remove(item_path)

    for fname in os.listdir(staging_dir):
        src = os.path.join(staging_dir, fname)
        dst = os.path.join(resharded_dir, fname)
        shutil.move(src, dst)


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <resharded_dir>", file=sys.stderr)
        sys.exit(1)

    resharded_dir = sys.argv[1]

    print(f"Loading manifest from {resharded_dir}...")
    manifest_entries = load_manifest(resharded_dir)

    print(f"Grouping {len(manifest_entries)} chunks by original filename...")
    groups = group_by_original(manifest_entries)
    print(f"Reconstructing {len(groups)} original file(s)...")

    parent_dir = os.path.dirname(os.path.abspath(resharded_dir))
    with tempfile.TemporaryDirectory(dir=parent_dir) as staging_dir:
        reconstruct_files(groups, resharded_dir, staging_dir)
        print("Replacing resharded tree with original files...")
        replace_tree_with_originals(resharded_dir, staging_dir)

    print(f"Done. {len(groups)} file(s) restored to {resharded_dir}.")


if __name__ == "__main__":
    main()
DECOMPRESS_EOF

# Sync uv dependencies
cd /app
uv sync

echo "Setup complete. compress.py and decompress.py are ready in /app."
