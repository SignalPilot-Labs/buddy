"""Regression test: AF_READY marker must carry sandbox_secret in event dict.

Verifies that _parse_marker() extracts the 'secret' field from AF_READY
JSON and returns it as 'sandbox_secret' in the event dict. This is how
the connector receives the secret without it ever appearing in SSH args.
"""

from cli.connector.startup import _parse_marker, MARKER_RE


class TestAfReadySecretExtraction:
    """_parse_marker extracts secret from AF_READY JSON payload."""

    def test_af_ready_with_secret_sets_sandbox_secret(self) -> None:
        """AF_READY with 'secret' field → event['sandbox_secret'] == secret value."""
        line = 'AF_READY {"host":"node1","port":8080,"secret":"abc123def456"}'
        match = MARKER_RE.search(line)
        assert match is not None

        event = _parse_marker(match, "user@hpc")

        assert event["event"] == "ready"
        assert event["sandbox_secret"] == "abc123def456"
        assert event["host"] == "node1"
        assert event["port"] == 8080

    def test_af_ready_without_secret_sets_sandbox_secret_none(self) -> None:
        """AF_READY without 'secret' field → event['sandbox_secret'] is None."""
        line = 'AF_READY {"host":"node1","port":8080}'
        match = MARKER_RE.search(line)
        assert match is not None

        event = _parse_marker(match, "user@hpc")

        assert event["event"] == "ready"
        assert event["sandbox_secret"] is None

    def test_af_ready_with_64_char_hex_secret(self) -> None:
        """AF_READY with 64-char hex secret (secrets.token_hex(32)) is parsed correctly."""
        secret = "a" * 64
        line = f'AF_READY {{"host":"compute-7","port":8080,"secret":"{secret}"}}'
        match = MARKER_RE.search(line)
        assert match is not None

        event = _parse_marker(match, "user@hpc")

        assert event["sandbox_secret"] == secret

    def test_af_ready_with_backend_id_and_secret(self) -> None:
        """AF_READY with both backend_id and secret passes both through."""
        line = 'AF_READY {"host":"node1","port":8080,"secret":"mysecret","backend_id":"job-42"}'
        match = MARKER_RE.search(line)
        assert match is not None

        event = _parse_marker(match, "user@hpc")

        assert event["sandbox_secret"] == "mysecret"
        assert event["backend_id"] == "job-42"
