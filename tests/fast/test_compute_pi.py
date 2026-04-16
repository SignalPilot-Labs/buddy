"""Tests for compute_pi — Chudnovsky-based pi computation utility."""

import pytest

from scripts.compute_pi import _parse_args, compute_pi


PI_REFERENCE_50 = "3.14159265358979323846264338327950288419716939937510"


class TestComputePi:
    """Tests for compute_pi correctness, length, and CLI argument validation."""

    def test_first_50_digits(self) -> None:
        """Exact match against the canonical first 50 fractional digits of pi."""
        assert compute_pi(50) == PI_REFERENCE_50

    def test_first_100_digits_prefix_matches(self) -> None:
        """100-digit result starts with the known 50-digit prefix and has correct length."""
        result = compute_pi(100)
        assert result.startswith(PI_REFERENCE_50)
        assert len(result) == len("3.") + 100

    def test_500_digits_length_and_prefix(self) -> None:
        """500-digit result has correct length and the 50-digit prefix is intact."""
        result = compute_pi(500)
        assert len(result) == len("3.") + 500
        assert result.startswith(PI_REFERENCE_50)

    def test_rejects_zero(self) -> None:
        """--digits 0 must exit with an error (fail-fast validation)."""
        with pytest.raises(SystemExit):
            _parse_args(["--digits", "0"])

    def test_rejects_negative(self) -> None:
        """Negative --digits must also exit with an error."""
        with pytest.raises(SystemExit):
            _parse_args(["--digits", "-5"])

    def test_single_digit(self) -> None:
        """--digits 1 returns '3.1'."""
        assert compute_pi(1) == "3.1"

    def test_short_form_flag(self) -> None:
        """-n flag is accepted as an alias for --digits."""
        assert _parse_args(["-n", "50"]) == 50
