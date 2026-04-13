"""Tests for scripts.compute_pi — Ramanujan pi computation."""

import pytest

from scripts.compute_pi import compute_pi


class TestComputePi:
    """Tests for the Ramanujan-based pi computation."""

    def test_fifty_digits(self) -> None:
        """compute_pi(50) must match the first 50 decimal digits of pi."""
        expected = "3.14159265358979323846264338327950288419716939937510"
        assert compute_pi(50) == expected

    def test_one_digit(self) -> None:
        """compute_pi(1) returns the integer part plus one decimal place."""
        assert compute_pi(1) == "3.1"

    def test_zero_raises_value_error(self) -> None:
        """compute_pi(0) must raise ValueError."""
        with pytest.raises(ValueError):
            compute_pi(0)

    def test_negative_raises_value_error(self) -> None:
        """compute_pi with a negative number must raise ValueError."""
        with pytest.raises(ValueError):
            compute_pi(-5)
