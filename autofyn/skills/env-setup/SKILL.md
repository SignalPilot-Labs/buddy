---
description: "Use when setting up a project environment — installing dependencies, verifying builds, detecting the tech stack. Covers Phase 0 of a new session."
---

# Environment Setup

## Stack Detection

Read these files to understand what needs to be installed:

| File | Indicates |
|------|-----------|
| `package.json` | Node project — run `npm ci` |
| `pyproject.toml` | Python project — run `pip install -e .` or `uv pip install -e .` |
| `requirements.txt` | Python deps — run `pip install -r requirements.txt` |
| `Cargo.toml` | Rust project — run `cargo build` |
| `go.mod` | Go project — run `go mod download` |

Check `CLAUDE.md` and `README.md` first — they may specify exact setup commands.

## Install Order

1. Read project config files
2. Install backend dependencies
3. Install frontend dependencies (if separate)
4. Run the build to verify it works
5. Run tests to verify the environment is healthy

## If Build Fails

- Read the error carefully — most setup failures are missing system deps or wrong versions
- Check if there's a `.tool-versions`, `.nvmrc`, or `Dockerfile` that specifies required versions
- If a dep is missing from the lockfile, do NOT add it yourself — flag it

## Pre-installed Tools

See the verification-rules appended to build/review agent prompts for the full list. Key ones already in the sandbox: `pytest`, `pyright`, `ruff`, `tsc`, `eslint`. Do NOT pip/npm install these.
