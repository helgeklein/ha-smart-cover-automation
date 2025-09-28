"""Tests for utility functions in the Smart Cover Automation integration."""

from __future__ import annotations

import pytest

from custom_components.smart_cover_automation.util import to_float_or_none


class TestToFloatOrNone:
    """Test suite for the to_float_or_none utility function."""

    def test_int_conversion(self) -> None:
        """Test that integers are converted to float."""
        assert to_float_or_none(42) == 42.0
        assert to_float_or_none(0) == 0.0
        assert to_float_or_none(-10) == -10.0

    def test_float_conversion(self) -> None:
        """Test that floats are returned as-is."""
        assert to_float_or_none(3.14) == 3.14
        assert to_float_or_none(0.0) == 0.0
        assert to_float_or_none(-2.5) == -2.5

    def test_numeric_string_conversion(self) -> None:
        """Test that numeric strings are converted to float.

        This covers the real-world scenario where configuration values
        might come in as strings from YAML files, JSON imports, or
        other configuration sources that serialize numbers as strings.
        """
        # Integer strings
        assert to_float_or_none("180") == 180.0
        assert to_float_or_none("0") == 0.0
        assert to_float_or_none("-45") == -45.0

        # Float strings
        assert to_float_or_none("3.14") == 3.14
        assert to_float_or_none("180.5") == 180.5
        assert to_float_or_none("-90.25") == -90.25

        # Scientific notation
        assert to_float_or_none("1e2") == 100.0
        assert to_float_or_none("2.5e-1") == 0.25

    def test_whitespace_string_conversion(self) -> None:
        """Test that strings with whitespace are handled correctly."""
        assert to_float_or_none(" 180 ") == 180.0
        assert to_float_or_none("\t3.14\n") == 3.14

    def test_invalid_string_conversion(self) -> None:
        """Test that non-numeric strings return None."""
        assert to_float_or_none("not_a_number") is None
        assert to_float_or_none("180degrees") is None
        assert to_float_or_none("") is None

        # Special cases: Python's float() accepts these
        import math

        nan_result = to_float_or_none("NaN")
        assert nan_result is not None and math.isnan(nan_result)
        assert to_float_or_none("inf") == float("inf")
        assert to_float_or_none("-inf") == float("-inf")

    def test_none_and_other_types(self) -> None:
        """Test that None and other non-coercible types return None."""
        assert to_float_or_none(None) is None
        assert to_float_or_none([]) is None
        assert to_float_or_none({}) is None
        assert to_float_or_none(object()) is None

    def test_boolean_conversion(self) -> None:
        """Test that booleans are converted to float.

        Note: In Python, bool is a subclass of int, so True/False
        are treated as 1/0 respectively by the to_float_or_none function.
        """
        assert to_float_or_none(True) == 1.0
        assert to_float_or_none(False) == 0.0

    def test_edge_cases(self) -> None:
        """Test edge cases and boundary conditions."""
        # Very large numbers
        assert to_float_or_none("1e308") == 1e308

        # Very small numbers
        assert to_float_or_none("1e-308") == 1e-308

        # Zero variations
        assert to_float_or_none("0.0") == 0.0
        assert to_float_or_none("-0.0") == -0.0

    @pytest.mark.parametrize(
        "invalid_input",
        [
            [],  # list
            {},  # dict
            set(),  # set
            lambda x: x,  # function
            object(),  # generic object
        ],
    )
    def test_parametrized_invalid_types(self, invalid_input) -> None:
        """Parametrized test for various invalid input types."""
        assert to_float_or_none(invalid_input) is None
