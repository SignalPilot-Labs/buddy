"""Tests for the Ramanujan pi computation script."""

import pytest

from compute_pi import PiComputer

# 50 significant digits of pi (1 integer + 49 decimal places)
KNOWN_PI_50: str = "3.1415926535897932384626433832795028841971693993751"


class TestPiComputer:
    """Tests for PiComputer correctness and error handling."""

    def test_known_digits(self) -> None:
        """Computing 50 digits must match the known first 50 significant digits of pi."""
        computer = PiComputer(50)
        result = computer.compute()
        assert result == KNOWN_PI_50

    def test_single_digit(self) -> None:
        """Computing 1 digit must return '3'."""
        computer = PiComputer(1)
        result = computer.compute()
        assert result == "3"

    def test_invalid_input_zero(self) -> None:
        """Constructing PiComputer with 0 must raise ValueError."""
        with pytest.raises(ValueError, match="num_digits must be >= 1"):
            PiComputer(0)

    def test_invalid_input_negative(self) -> None:
        """Constructing PiComputer with a negative number must raise ValueError."""
        with pytest.raises(ValueError, match="num_digits must be >= 1"):
            PiComputer(-1)

    def test_large_precision(self) -> None:
        """Computing 1000 digits must start with known digits and have correct length."""
        computer = PiComputer(1000)
        result = computer.compute()
        # "3." + 999 decimal digits = 1001 characters total
        assert len(result) == 1001
        # KNOWN_PI_50 is 51 characters: "3." + 49 decimal digits
        assert result[:51] == KNOWN_PI_50
