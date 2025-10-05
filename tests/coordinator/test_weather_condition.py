"""
Test weather condition functionality in the coordinator.

This module tests the weather condition checking logic that was recently added
to ensure covers only close when weather conditions are sunny.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.smart_cover_automation.const import COVER_ATTR_POS_TARGET_DESIRED
from custom_components.smart_cover_automation.coordinator import (
    DataUpdateCoordinator,
    InvalidSensorReadingError,
    WeatherEntityNotFoundError,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from ..conftest import MockConfigEntry, create_mock_weather_service, create_temperature_config, set_weather_forecast_temp


class TestWeatherCondition:
    """Test weather condition checking functionality."""

    @pytest.mark.parametrize(
        "weather_state_value, description",
        [
            (None, "missing weather entity"),
            ("unavailable", "unavailable weather entity"),
            ("unknown", "unknown weather entity"),
            (None, "weather entity with None state"),
        ],
    )
    async def test_weather_entity_invalid_states(self, weather_state_value: str | None, description: str) -> None:
        """Test handling of various invalid weather entity states.

        This parametrized test verifies that the coordinator gracefully handles
        different types of weather entity problems without crashing, ensuring
        robust automation behavior when weather data is unavailable.
        """
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Handle the special case of missing entity (None return)
        if weather_state_value is None and description == "missing weather entity":
            # Set up states where weather entity is missing but others exist
            hass.states.get.side_effect = lambda entity_id: {
                "weather.forecast": None,  # Weather entity missing
                "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
                "cover.test_cover": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
            }.get(entity_id)
            # Missing weather entity should be treated as critical error
            await coordinator.async_refresh()
            assert isinstance(coordinator.last_exception, UpdateFailed)
            assert "Temperature sensor 'weather.forecast' not found" in str(coordinator.last_exception)
        else:
            # Mock weather entity with the specified state
            weather_state = MagicMock()
            weather_state.state = weather_state_value

            hass.states.get.side_effect = lambda entity_id: {
                "weather.forecast": weather_state,
                "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
                "cover.test_cover": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
            }.get(entity_id)

            # Should handle invalid weather entity gracefully (not raise)
            await coordinator.async_refresh()
            # Should return early with weather unavailable message
            result = coordinator.data
            assert result == {"covers": {}, "message": "Weather data unavailable, skipping actions"}

    def test_get_weather_condition_direct_call(self) -> None:
        """Test _get_weather_condition method directly."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test successful weather condition retrieval
        weather_state = MagicMock()
        weather_state.state = "sunny"
        hass.states.get.return_value = weather_state

        result = coordinator._get_weather_condition("weather.test")
        assert result == "sunny"

        # Test weather entity not found
        hass.states.get.return_value = None
        with pytest.raises(WeatherEntityNotFoundError, match="weather.test"):
            coordinator._get_weather_condition("weather.test")

        # Test unavailable state
        weather_state.state = "unavailable"
        hass.states.get.return_value = weather_state
        with pytest.raises(InvalidSensorReadingError, match="Weather entity weather.test: state is unavailable"):
            coordinator._get_weather_condition("weather.test")

    @pytest.mark.parametrize(
        "weather_condition,expected_position,test_description",
        [
            ("cloudy", 100, "cloudy weather should keep covers open"),
            ("rainy", 100, "rainy weather should keep covers open"),
            ("snowy", 100, "snowy weather should keep covers open"),
            ("foggy", 100, "foggy weather should keep covers open"),
            ("stormy", 100, "stormy weather should keep covers open"),
        ],
    )
    async def test_non_sunny_weather_conditions_parametrized(
        self, weather_condition: str, expected_position: int, test_description: str
    ) -> None:
        """Test that various non-sunny weather conditions prevent cover closing.

        This parametrized test verifies that different non-sunny weather conditions
        all behave consistently by preventing automated cover closing, even when
        temperature and sun position would normally trigger closing.
        """
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service
        set_weather_forecast_temp(30.0)  # Hot temperature that would normally trigger closing
        hass.services.async_call.side_effect = create_mock_weather_service()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test with specified weather condition (not in WEATHER_SUNNY_CONDITIONS)
        weather_state = MagicMock()
        weather_state.state = weather_condition

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test_cover": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Even with hot temperature and sun hitting, cover should stay open due to non-sunny weather
        cover_data = result["covers"]["cover.test_cover"]
        assert cover_data[COVER_ATTR_POS_TARGET_DESIRED] == expected_position, f"Failed for {test_description}"

    @pytest.mark.parametrize(
        "sunny_condition,expected_position,test_description",
        [
            ("sunny", 0, "sunny weather should allow cover closing"),
            ("partlycloudy", 0, "partly cloudy weather should allow cover closing"),
        ],
    )
    async def test_sunny_weather_conditions_parametrized(self, sunny_condition: str, expected_position: int, test_description: str) -> None:
        """Test that various sunny weather conditions allow cover closing.

        This parametrized test verifies that different sunny weather conditions
        all behave consistently by allowing automated cover closing when
        temperature and sun position conditions are met.
        """
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service
        set_weather_forecast_temp(30.0)  # Hot temperature
        hass.services.async_call.side_effect = create_mock_weather_service()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        weather_state = MagicMock()
        weather_state.state = sunny_condition

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test_cover": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # With hot temp + sunny weather + sun hitting, cover should close
        cover_data = result["covers"]["cover.test_cover"]
        assert cover_data[COVER_ATTR_POS_TARGET_DESIRED] == expected_position, f"Failed for {test_description}"
