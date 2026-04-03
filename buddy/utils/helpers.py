"""Shared utilities for the agent package — serialization, truncation, transcript parsing, validation."""

import json
import logging
import re
from pathlib import Path
from typing import Any

from utils.constants import BRANCH_NAME_MAX_LEN, BRANCH_NAME_PATTERN, MAX_LIST_LEN, MAX_STR_LEN, TRANSCRIPT_LIMIT

log = logging.getLogger("agent")

_BRANCH_RE = re.compile(BRANCH_NAME_PATTERN)


def validate_branch_name(name: str) -> None:
    """Validate a branch name to prevent command injection."""
    if not name or len(name) > BRANCH_NAME_MAX_LEN:
        raise ValueError(f"Invalid branch name length: {len(name) if name else 0}")
    if not _BRANCH_RE.match(name):
        raise ValueError(f"Invalid branch name: contains disallowed characters")
    if '..' in name or name.endswith('.lock') or name.endswith('/'):
        raise ValueError(f"Invalid branch name format")


def safe_serialize(data: Any) -> Any:
    """Make data JSON-serializable with size limits to protect the DB."""
    if isinstance(data, str):
        if len(data) > MAX_STR_LEN:
            return data[:MAX_STR_LEN] + "...[truncated]"
        return data
    if isinstance(data, dict):
        return {k: safe_serialize(v) for k, v in data.items()}
    if isinstance(data, list):
        return [safe_serialize(item) for item in data[:MAX_LIST_LEN]]
    try:
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return str(data)


def summarize_input(input_data: dict, limit: int) -> dict:
    """Create a truncated summary of input for audit logging."""
    return {
        k: (v[:limit] + "...[truncated]" if isinstance(v, str) and len(v) > limit else v)
        for k, v in input_data.items()
    }


def read_transcript_final_text(transcript_path: str) -> str:
    """Extract the final assistant message from a subagent's JSONL transcript."""
    if not transcript_path:
        return ""
    try:
        raw = Path(transcript_path).read_text(encoding="utf-8", errors="replace")
        lines = raw.strip().split("\n")
        for line in reversed(lines[-20:]):
            try:
                entry = json.loads(line)
                if entry.get("role") != "assistant":
                    continue
                content = entry.get("content", [])
                if isinstance(content, list):
                    texts = [
                        b.get("text", "")
                        for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                    if texts:
                        return "\n".join(texts)[:TRANSCRIPT_LIMIT]
                elif isinstance(content, str):
                    return content[:TRANSCRIPT_LIMIT]
            except (json.JSONDecodeError, KeyError):
                continue
    except Exception:
        log.warning("Failed to read subagent transcript: %s", transcript_path, exc_info=True)
    return ""
