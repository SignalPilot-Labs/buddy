"""Shared secret-scrubbing utility for the autofyn package.

The function is intentionally pure: callers gather secret values from their
own environment or request body and pass them in. No os.environ reads happen
here — that follows the dependency-injection rule and makes tests clean.
"""

from collections.abc import Iterable

from db.constants import SECRET_REDACT_MASK


def scrub_secrets(text: str, secrets: Iterable[str | None]) -> str:
    """Replace each non-empty secret value in `text` with SECRET_REDACT_MASK.

    Skips None and empty-string values so callers can safely pass
    os.environ.get() results without an extra None-check.
    """
    scrubbed = text
    for value in secrets:
        if value:
            scrubbed = scrubbed.replace(value, SECRET_REDACT_MASK)
    return scrubbed
