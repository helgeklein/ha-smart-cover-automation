"""
Test weather condition functionality in the coordinator.

This module tests the weather condition checking logic that was recently added
to ensure covers only close when weather conditions are sunny.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest

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

    @pytest.mark.asyncio
    async def test_weather_entity_not_found(self) -> None:
        """Test handling when weather entity is not found."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock missing weather entity
        hass.states.get.return_value = None

        # Should handle missing weather entity gracefully (not raise)
        await coordinator.async_refresh()
        # The coordinator should return empty result when all covers are unavailable
        result = coordinator.data
        assert result == {"covers": {}}

    @pytest.mark.asyncio
    async def test_weather_entity_unavailable_state(self) -> None:
        """Test handling when weather entity is in unavailable state."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock weather entity with unavailable state
        weather_state = MagicMock()
        weather_state.state = "unavailable"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test_cover": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Should handle unavailable weather entity gracefully (not raise)
        await coordinator.async_refresh()
        # Should still return empty covers since weather reading fails
        result = coordinator.data
        assert result is None or result == {"covers": {}}

    @pytest.mark.asyncio
    async def test_weather_entity_unknown_state(self) -> None:
        """Test handling when weather entity is in unknown state."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock weather entity with unknown state
        weather_state = MagicMock()
        weather_state.state = "unknown"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test_cover": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Should handle unknown weather entity gracefully (not raise)
        await coordinator.async_refresh()
        # Should still return empty covers since weather reading fails
        result = coordinator.data
        assert result is None or result == {"covers": {}}

    @pytest.mark.asyncio
    async def test_weather_entity_none_state(self) -> None:
        """Test handling when weather entity state is None."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock weather entity with None state
        weather_state = MagicMock()
        weather_state.state = None

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test_cover": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Should handle None weather entity gracefully (not raise)
        await coordinator.async_refresh()
        # Should still return empty covers since weather reading fails
        result = coordinator.data
        assert result is None or result == {"covers": {}}

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

    @pytest.mark.asyncio
    async def test_non_sunny_weather_conditions(self) -> None:
        """Test that non-sunny weather conditions prevent cover closing."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service
        set_weather_forecast_temp(30.0)  # Hot temperature
        hass.services.async_call.side_effect = create_mock_weather_service()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test with cloudy weather (not in WEATHER_SUNNY_CONDITIONS)
        weather_state = MagicMock()
        weather_state.state = "cloudy"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test_cover": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Even with hot temperature and sun hitting, cover should stay open due to cloudy weather
        cover_data = result["covers"]["cover.test_cover"]
        assert cover_data[COVER_ATTR_POS_TARGET_DESIRED] == 100  # Should stay open

    @pytest.mark.asyncio
    async def test_sunny_weather_conditions_variations(self) -> None:
        """Test different sunny weather condition variations."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service
        set_weather_forecast_temp(30.0)  # Hot temperature
        hass.services.async_call.side_effect = create_mock_weather_service()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test each sunny condition
        sunny_conditions = ["sunny", "partlycloudy"]

        for condition in sunny_conditions:
            weather_state = MagicMock()
            weather_state.state = condition

            hass.states.get.side_effect = lambda entity_id, ws=weather_state: {
                "weather.forecast": ws,
                "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
                "cover.test_cover": MagicMock(attributes={"current_position": 100, "supported_features": 15}),
            }.get(entity_id)

            await coordinator.async_refresh()
            result = coordinator.data

            # With hot temp + sunny weather + sun hitting, cover should close
            cover_data = result["covers"]["cover.test_cover"]
            assert cover_data[COVER_ATTR_POS_TARGET_DESIRED] == 0, f"Failed for condition: {condition}"
