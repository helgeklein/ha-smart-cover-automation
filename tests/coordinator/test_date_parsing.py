"""
Test date parsing and edge cases in the coordinator.

This module tests date parsing logic in weather forecast handling
to improve test coverage for edge cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from ..conftest import create_invalid_weather_service


class TestDateParsingEdgeCases:
    """Test date parsing edge cases in weather forecast handling."""

    def test_find_today_forecast_with_datetime_objects(self, mock_coordinator_basic) -> None:
        """Test forecast parsing with actual datetime objects."""
        # Create forecast with datetime object
        today = datetime.now(timezone.utc)
        forecast_list = [
            {
                "datetime": today,  # datetime object instead of string
                "native_temperature": 25.0,
            },
            {
                "datetime": today.isoformat(),  # string format
                "native_temperature": 26.0,
            },
        ]

        result = mock_coordinator_basic._find_today_forecast(forecast_list)
        assert result is not None
        assert result["native_temperature"] == 25.0

    def test_find_today_forecast_with_invalid_datetime_field(self, mock_coordinator_basic) -> None:
        """Test forecast parsing with invalid datetime fields."""
        # Create forecast with invalid datetime fields
        forecast_list = [
            {
                "datetime": 12345,  # Invalid type (integer)
                "native_temperature": 25.0,
            },
            {
                "datetime": {"invalid": "object"},  # Invalid type (dict)
                "native_temperature": 26.0,
            },
            {
                "datetime": datetime.now(timezone.utc).isoformat(),  # Valid string
                "native_temperature": 27.0,
            },
        ]

        result = mock_coordinator_basic._find_today_forecast(forecast_list)
        assert result is not None
        assert result["native_temperature"] == 27.0  # Should find the valid one

    def test_find_today_forecast_no_datetime_field(self, mock_coordinator_basic) -> None:
        """Test forecast parsing when datetime field is missing."""
        # Create forecast without datetime field
        forecast_list = [
            {
                "temperature": 25.0,  # Missing datetime field
            },
            {
                "date": "2023-01-01",  # Different field name
                "temperature": 26.0,
            },
        ]

        result = mock_coordinator_basic._find_today_forecast(forecast_list)
        assert result is not None
        assert result["temperature"] == 25.0  # Should return first entry as fallback

    def test_find_today_forecast_with_date_field(self, mock_coordinator_basic) -> None:
        """Test forecast parsing with date field instead of datetime."""
        # Create forecast with date field
        today = datetime.now(timezone.utc).date().isoformat()
        forecast_list = [
            {
                "date": today,
                "native_temperature": 25.0,
            },
            {
                "date": "2023-12-31",  # Different date
                "native_temperature": 26.0,
            },
        ]

        result = mock_coordinator_basic._find_today_forecast(forecast_list)
        assert result is not None
        assert result["native_temperature"] == 25.0

    def test_find_today_forecast_with_mixed_date_formats(self, mock_coordinator_basic) -> None:
        """Test forecast parsing with mixed date formats."""
        # Create forecast with mixed date formats
        today = datetime.now(timezone.utc)
        forecast_list = [
            {
                "datetime": "invalid-date-format",  # Invalid date string
                "native_temperature": 25.0,
            },
            {
                "datetime": today.isoformat().replace("+00:00", "Z"),  # Z format
                "native_temperature": 26.0,
            },
        ]

        result = mock_coordinator_basic._find_today_forecast(forecast_list)
        assert result is not None
        assert result["native_temperature"] == 26.0  # Should find the valid Z format

    def test_extract_max_temperature_edge_cases(self, mock_coordinator_basic) -> None:
        """Test temperature extraction with various edge cases."""
        # Test with invalid string temperatures that should return None
        forecast = {"native_temperature": "invalid"}
        result = mock_coordinator_basic._extract_max_temperature(forecast)
        assert result is None

        # Test with valid integer temperature
        forecast = {"native_temperature": 25}
        result = mock_coordinator_basic._extract_max_temperature(forecast)
        assert result == 25.0

        # Test with integer temperature
        forecast = {"temp_max": 26}
        result = mock_coordinator_basic._extract_max_temperature(forecast)
        assert result == 26.0

        # Test with non-numeric string
        forecast = {"native_temperature": "not_a_number"}
        result = mock_coordinator_basic._extract_max_temperature(forecast)
        assert result is None

        # Test with None values
        forecast = {"native_temperature": None}
        result = mock_coordinator_basic._extract_max_temperature(forecast)
        assert result is None

        # Test with list (invalid type)
        forecast = {"native_temperature": [25.0]}
        result = mock_coordinator_basic._extract_max_temperature(forecast)
        assert result is None

    @pytest.mark.asyncio
    async def test_weather_forecast_missing_fields(self, mock_coordinator_basic) -> None:
        """Test weather forecast handling with missing or invalid fields."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service with missing temperature fields
        invalid_forecast_data = [
            {
                "datetime": datetime.now(timezone.utc).isoformat(),
                "humidity": 80,  # No temperature field
            },
            {
                "datetime": datetime.now(timezone.utc).isoformat(),
                "native_temperature": "invalid",  # Invalid temperature
            },
        ]
        hass.services.async_call.side_effect = create_invalid_weather_service(invalid_forecast_data)

        # Use the mock coordinator but update its hass reference for this test
        mock_coordinator_basic.hass = hass

        # Mock weather entity
        weather_state = MagicMock()
        weather_state.state = "sunny"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Should complete update but with no valid temperature data
        await mock_coordinator_basic.async_refresh()
        result = mock_coordinator_basic.data

        # Should return empty result due to missing valid temperature
        assert result == {"covers": {}}
