from scripts.pi.compute import PiComputer

KNOWN_PI_50 = "3.14159265358979323846264338327950288419716939937510"
KNOWN_PREFIX = "3.14159265358979323846"


class TestPiComputer:
    def setup_method(self) -> None:
        self.computer = PiComputer()

    def test_first_50_digits_match_known_value(self) -> None:
        result = self.computer.compute(50)
        assert result == KNOWN_PI_50

    def test_result_starts_with_known_prefix(self) -> None:
        result = self.computer.compute(50)
        assert result.startswith(KNOWN_PREFIX)

    def test_digit_count_1(self) -> None:
        result = self.computer.compute(1)
        assert result == "3.1"

    def test_digit_count_10(self) -> None:
        result = self.computer.compute(10)
        assert result == "3.1415926535"

    def test_digit_count_100(self) -> None:
        result = self.computer.compute(100)
        assert result.startswith(KNOWN_PREFIX)
        dot_index = result.index(".")
        assert len(result) - dot_index - 1 == 100

    def test_digit_count_1000(self) -> None:
        result = self.computer.compute(1000)
        assert result.startswith(KNOWN_PREFIX)
        dot_index = result.index(".")
        assert len(result) - dot_index - 1 == 1000
