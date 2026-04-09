"""Shell escaping helpers for sandbox exec commands."""


def shell_quote(s: str) -> str:
    """Shell-escape a string for safe use in echo commands."""
    return "'" + s.replace("'", "'\\''") + "'"
