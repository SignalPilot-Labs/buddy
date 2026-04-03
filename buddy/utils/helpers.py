"""Shared utilities for the agent package — serialization, truncation, transcript parsing."""

import json
import logging
from pathlib import Path
from typing import Any

from utils.constants import MAX_LIST_LEN, MAX_STR_LEN, TRANSCRIPT_LIMIT

log = logging.getLogger("agent")


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
