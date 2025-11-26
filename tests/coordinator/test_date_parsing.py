"""
Test date parsing and edge cases in the coordinator.

This module tests date parsing logic in weather forecast handling
to improve test coverage for edge cases.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from custom_components.smart_cover_automation.data import CoordinatorData

from ..conftest import create_invalid_weather_service


class TestDateParsingEdgeCases:
    """Test date parsing edge cases in weather forecast handling."""

    def test_find_day_forecast_with_datetime_objects(self, mock_coordinator_basic) -> None:
        """Test forecast parsing with actual datetime objects."""
        from ..conftest import create_forecast_with_applicable_date

        # Create forecasts for the applicable date
        # Use datetime objects to test that code path
        forecast_temp = 25.0
        forecast_dict = create_forecast_with_applicable_date(forecast_temp)

        # Convert the datetime string to an actual datetime object to test that parsing path
        forecast_datetime_obj = datetime.fromisoformat(forecast_dict["datetime"])

        forecast_list = [
            {
                "datetime": forecast_datetime_obj,  # datetime object instead of string
                "native_temperature": forecast_temp,
            },
            {
                "datetime": forecast_dict["datetime"],  # string format
                "native_temperature": 26.0,
            },
        ]

        result = mock_coordinator_basic._ha_interface._find_day_forecast(forecast_list)
        assert result is not None
        applicable_day, forecast = result
        # Should match whichever day is applicable based on current time
        assert applicable_day in ("today", "tomorrow")
        assert forecast["native_temperature"] == forecast_temp

    @patch("custom_components.smart_cover_automation.ha_interface.dt_util")
    def test_find_day_forecast_with_invalid_datetime_field(self, mock_dt_util: MagicMock, mock_coordinator_basic) -> None:
        """Test forecast parsing with invalid datetime fields."""
        # Set current time to use today's forecast
        today = datetime.now(timezone.utc)
        mock_dt_util.now.return_value = today

        # Create forecast with invalid datetime fields
        # When all entries fail to parse or don't match the applicable day,
        # returns None (no fallback)
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
                "datetime": "invalid-date-string",  # Invalid date string
                "native_temperature": 27.0,
            },
        ]

        result = mock_coordinator_basic._ha_interface._find_day_forecast(forecast_list)
        # When all date parsing fails, returns None (no more fallback)
        assert result is None

    @patch("custom_components.smart_cover_automation.ha_interface.dt_util")
    def test_find_day_forecast_no_datetime_field(self, mock_dt_util: MagicMock, mock_coordinator_basic) -> None:
        """Test forecast parsing when datetime field is missing."""
        # Set current time to use today's forecast
        today = datetime.now(timezone.utc)
        mock_dt_util.now.return_value = today

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

        result = mock_coordinator_basic._ha_interface._find_day_forecast(forecast_list)
        # When no datetime/date field is present, returns None
        assert result is None

    def test_find_day_forecast_with_date_field(self, mock_coordinator_basic) -> None:
        """Test forecast parsing with 'date' field instead of 'datetime'."""
        from ..conftest import create_forecast_with_applicable_date

        # Create forecast for the applicable date
        forecast_temp = 24.0
        forecast_dict = create_forecast_with_applicable_date(forecast_temp)

        # Create forecast with 'date' field instead of 'datetime' to test alternate field name
        forecast_list = [
            {
                "date": forecast_dict["datetime"],  # Using 'date' instead of 'datetime'
                "native_temperature": forecast_temp,
            }
        ]

        result = mock_coordinator_basic._ha_interface._find_day_forecast(forecast_list)
        assert result is not None
        applicable_day, forecast = result
        assert applicable_day in ("today", "tomorrow")  # Accept either depending on actual time
        assert forecast["native_temperature"] == forecast_temp

    @patch("custom_components.smart_cover_automation.ha_interface.dt_util")
    def test_find_day_forecast_with_mixed_date_formats(self, mock_dt_util: MagicMock, mock_coordinator_basic) -> None:
        """Test forecast parsing with mixed date formats."""
        # Set current time to use today's forecast
        today = datetime.now(timezone.utc)
        mock_dt_util.now.return_value = today

        # Create forecast with mixed date formats
        # When all dates fail to parse or don't match applicable day,
        # returns None (no more fallback)
        forecast_list = [
            {
                "datetime": "invalid-date-format",  # Invalid date string
                "native_temperature": 25.0,
            },
            {
                "datetime": "also-invalid",  # Also invalid
                "native_temperature": 26.0,
            },
        ]

        result = mock_coordinator_basic._ha_interface._find_day_forecast(forecast_list)
        # When all date parsing fails, returns None
        assert result is None

    def test_extract_max_temperature_edge_cases(self, mock_coordinator_basic) -> None:
        """Test temperature extraction with various edge cases."""
        # Test with invalid string temperatures that should return None
        forecast = {"native_temperature": "invalid"}
        result = mock_coordinator_basic._ha_interface._extract_max_temperature(forecast)
        assert result is None

        # Test with valid integer temperature
        forecast = {"native_temperature": 25}
        result = mock_coordinator_basic._ha_interface._extract_max_temperature(forecast)
        assert result == 25.0

        # Test with integer temperature
        forecast = {"temp_max": 26}
        result = mock_coordinator_basic._ha_interface._extract_max_temperature(forecast)
        assert result == 26.0

        # Test with non-numeric string
        forecast = {"native_temperature": "not_a_number"}
        result = mock_coordinator_basic._ha_interface._extract_max_temperature(forecast)
        assert result is None

        # Test with None values
        forecast = {"native_temperature": None}
        result = mock_coordinator_basic._ha_interface._extract_max_temperature(forecast)
        assert result is None

        # Test with list (invalid type)
        forecast = {"native_temperature": [25.0]}
        result = mock_coordinator_basic._ha_interface._extract_max_temperature(forecast)
        assert result is None

    async def test_weather_forecast_missing_fields(self, mock_coordinator_basic, caplog) -> None:
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

        # Set caplog to capture INFO level messages
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Should complete update but with no valid temperature data
        await mock_coordinator_basic.async_refresh()
        result = mock_coordinator_basic.data

        # Should return empty result due to missing valid temperature
        assert result == CoordinatorData(covers={})
        assert "All covers unavailable; skipping actions" in caplog.text
