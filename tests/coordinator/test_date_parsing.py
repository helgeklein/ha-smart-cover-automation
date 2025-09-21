"""
Test date parsing and edge cases in the coordinator.

This module tests date parsing logic in weather forecast handling
to improve test coverage for edge cases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from ..conftest import MockConfigEntry, create_temperature_config


class TestDateParsingEdgeCases:
    """Test date parsing edge cases in weather forecast handling."""

    def test_find_today_forecast_with_datetime_objects(self) -> None:
        """Test forecast parsing with actual datetime objects."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

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

        result = coordinator._find_today_forecast(forecast_list)
        assert result is not None
        assert result["native_temperature"] == 25.0

    def test_find_today_forecast_with_invalid_datetime_field(self) -> None:
        """Test forecast parsing with invalid datetime fields."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

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

        result = coordinator._find_today_forecast(forecast_list)
        assert result is not None
        assert result["native_temperature"] == 27.0  # Should find the valid one

    def test_find_today_forecast_no_datetime_field(self) -> None:
        """Test forecast parsing when datetime field is missing."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

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

        result = coordinator._find_today_forecast(forecast_list)
        assert result is not None
        assert result["temperature"] == 25.0  # Should return first entry as fallback

    def test_find_today_forecast_with_date_field(self) -> None:
        """Test forecast parsing with date field instead of datetime."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

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

        result = coordinator._find_today_forecast(forecast_list)
        assert result is not None
        assert result["native_temperature"] == 25.0

    def test_find_today_forecast_with_mixed_date_formats(self) -> None:
        """Test forecast parsing with mixed date formats."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

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

        result = coordinator._find_today_forecast(forecast_list)
        assert result is not None
        assert result["native_temperature"] == 26.0  # Should find the valid Z format

    def test_extract_max_temperature_edge_cases(self) -> None:
        """Test temperature extraction with various edge cases."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test with invalid string temperatures that should return None
        forecast = {"native_temperature": "invalid"}
        result = coordinator._extract_max_temperature(forecast)
        assert result is None

        # Test with valid integer temperature
        forecast = {"native_temperature": 25}
        result = coordinator._extract_max_temperature(forecast)
        assert result == 25.0

        # Test with integer temperature
        forecast = {"temp_max": 26}
        result = coordinator._extract_max_temperature(forecast)
        assert result == 26.0

        # Test with non-numeric string
        forecast = {"native_temperature": "not_a_number"}
        result = coordinator._extract_max_temperature(forecast)
        assert result is None

        # Test with None values
        forecast = {"native_temperature": None}
        result = coordinator._extract_max_temperature(forecast)
        assert result is None

        # Test with list (invalid type)
        forecast = {"native_temperature": [25.0]}
        result = coordinator._extract_max_temperature(forecast)
        assert result is None

    @pytest.mark.asyncio
    async def test_weather_forecast_missing_fields(self) -> None:
        """Test weather forecast handling with missing or invalid fields."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service with missing temperature fields
        async def mock_weather_service(domain, service, service_data, **kwargs):
            return {
                "weather.forecast": {
                    "forecast": [
                        {
                            "datetime": datetime.now(timezone.utc).isoformat(),
                            "humidity": 80,  # No temperature field
                        },
                        {
                            "datetime": datetime.now(timezone.utc).isoformat(),
                            "native_temperature": "invalid",  # Invalid temperature
                        },
                    ]
                }
            }

        hass.services.async_call.side_effect = mock_weather_service

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock weather entity
        weather_state = MagicMock()
        weather_state.state = "sunny"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Should complete update but with no valid temperature data
        await coordinator.async_refresh()
        result = coordinator.data

        # Should return empty result due to missing valid temperature
        assert result == {"covers": {}}
