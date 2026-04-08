"""Tests for compute_pi module."""

from compute_pi import compute_pi

PI_FIRST_50_DIGITS: str = "3.14159265358979323846264338327950288419716939937510"


class TestComputePi:
    """Tests for the compute_pi function."""

    def test_first_50_digits(self) -> None:
        result = compute_pi(50)
        assert result.startswith(PI_FIRST_50_DIGITS)

    def test_one_digit(self) -> None:
        result = compute_pi(1)
        assert result == "3.1"

    def test_100_digits_exact_length(self) -> None:
        result = compute_pi(100)
        assert result.startswith("3.")
        assert len(result.split(".")[1]) == 100

    def test_large_request_returns_correct_length(self) -> None:
        num_digits = 500
        result = compute_pi(num_digits)
        # Format: "3." followed by num_digits decimal digits
        assert result.startswith("3.")
        decimal_part = result[2:]
        assert len(decimal_part) == num_digits
