"""Tests for utility functions in the Smart Cover Automation integration."""

from __future__ import annotations

import pytest

from custom_components.smart_cover_automation.util import to_float_or_none


class TestToFloatOrNone:
    """Test suite for the to_float_or_none utility function."""

    @pytest.mark.parametrize(
        "input_value,expected_result,test_description",
        [
            # Integer conversion
            (42, 42.0, "positive integer"),
            (0, 0.0, "zero integer"),
            (-10, -10.0, "negative integer"),
            # Float conversion (should return as-is)
            (3.14, 3.14, "positive float"),
            (0.0, 0.0, "zero float"),
            (-2.5, -2.5, "negative float"),
            # Boolean conversion (bool is subclass of int)
            (True, 1.0, "boolean True"),
            (False, 0.0, "boolean False"),
            # Numeric string conversion
            ("180", 180.0, "integer string"),
            ("0", 0.0, "zero string"),
            ("-45", -45.0, "negative integer string"),
            ("3.14", 3.14, "float string"),
            ("180.5", 180.5, "decimal string"),
            ("-90.25", -90.25, "negative decimal string"),
            ("1e2", 100.0, "scientific notation"),
            ("2.5e-1", 0.25, "negative exponent scientific"),
            # Whitespace handling
            (" 180 ", 180.0, "string with spaces"),
            ("\t3.14\n", 3.14, "string with tab and newline"),
            # Edge cases - large and small numbers
            ("1e308", 1e308, "very large number"),
            ("1e-308", 1e-308, "very small number"),
            ("0.0", 0.0, "explicit zero decimal"),
            ("-0.0", -0.0, "negative zero"),
            # Invalid inputs that should return None
            ("not_a_number", None, "non-numeric string"),
            ("180degrees", None, "string with suffix"),
            ("", None, "empty string"),
            (None, None, "None value"),
            ([], None, "empty list"),
            ({}, None, "empty dict"),
            (set(), None, "empty set"),
            (lambda x: x, None, "function object"),
            (object(), None, "generic object"),
        ],
    )
    def test_to_float_or_none_comprehensive(self, input_value, expected_result, test_description):
        """Comprehensive parametrized test for to_float_or_none function."""
        result = to_float_or_none(input_value)

        if expected_result is None:
            assert result is None, f"Expected None for {test_description}, got {result}"
        else:
            assert result == expected_result, f"Expected {expected_result} for {test_description}, got {result}"
            assert isinstance(result, float), f"Result should be float for {test_description}"

    def test_special_float_values(self) -> None:
        """Test special float values that require special handling."""
        import math

        # NaN handling
        nan_result = to_float_or_none("NaN")
        assert nan_result is not None and math.isnan(nan_result)

        # Infinity handling
        assert to_float_or_none("inf") == float("inf")
        assert to_float_or_none("-inf") == float("-inf")
