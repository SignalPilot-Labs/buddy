import pytest

from scripts.pi.compute import compute_pi


class TestComputePi:
    def test_ten_digits(self) -> None:
        result = compute_pi(10)
        assert result == "3.1415926535"

    def test_fifty_digits(self) -> None:
        result = compute_pi(50)
        assert result == "3.14159265358979323846264338327950288419716939937510"

    def test_one_digit(self) -> None:
        result = compute_pi(1)
        assert result == "3.1"

    def test_invalid_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_pi(0)

    def test_invalid_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_pi(-5)
