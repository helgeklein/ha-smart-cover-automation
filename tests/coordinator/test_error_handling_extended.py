"""Test comprehensive error handling scenarios in coordinator operations."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

from custom_components.smart_cover_automation.coordinator import (
    DataUpdateCoordinator,
    ServiceCallError,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import MOCK_COVER_ENTITY_ID, MockConfigEntry, create_temperature_config


class TestCoordinatorErrorHandling:
    """Test comprehensive error handling scenarios in coordinator operations."""

    @pytest.mark.asyncio
    async def test_configuration_resolution_exception(self) -> None:
        """Test handling of configuration resolution exceptions."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Create a config entry with invalid data that will cause resolution to fail
        config = create_temperature_config()
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock the _resolved_settings method to raise an exception
        def mock_resolved_settings():
            raise ValueError("Invalid configuration data")

        coordinator._resolved_settings = mock_resolved_settings

        # Should handle configuration error gracefully
        await coordinator.async_refresh()
        # Data should be None due to configuration error
        result = coordinator.data
        assert result is None

    @pytest.mark.asyncio
    async def test_unexpected_error_during_automation(self) -> None:
        """Test handling of unexpected errors during automation update."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock weather and cover states to trigger automation
        weather_state = MagicMock()
        weather_state.state = "sunny"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            MOCK_COVER_ENTITY_ID: MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Mock weather forecast service
        async def mock_weather_service(domain, service, service_data, **kwargs):
            return {
                "weather.forecast": {
                    "forecast": [
                        {
                            "datetime": "2023-01-01T12:00:00Z",
                            "native_temperature": 30.0,  # Hot temperature
                        }
                    ]
                }
            }

        hass.services.async_call.side_effect = mock_weather_service

        # Mock _handle_automation to raise unexpected error
        async def mock_handle_automation(*args, **kwargs):
            raise RuntimeError("Unexpected system error")

        coordinator._handle_automation = mock_handle_automation

        # Should handle unexpected error gracefully
        await coordinator.async_refresh()
        # Should return empty covers due to unexpected error
        result = coordinator.data
        assert result == {"covers": {}}

    @pytest.mark.asyncio
    async def test_service_call_home_assistant_error(self) -> None:
        """Test handling of HomeAssistantError during service calls."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock service call to raise HomeAssistantError
        hass.services.async_call.side_effect = HomeAssistantError("Home Assistant error")

        # Should raise ServiceCallError
        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(MOCK_COVER_ENTITY_ID, 50, 15)

    @pytest.mark.asyncio
    async def test_service_call_connection_error(self) -> None:
        """Test handling of ConnectionError during service calls."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock service call to raise ConnectionError
        hass.services.async_call.side_effect = ConnectionError("Connection lost")

        # Should raise ServiceCallError
        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(MOCK_COVER_ENTITY_ID, 50, 15)

    @pytest.mark.asyncio
    async def test_service_call_value_error(self) -> None:
        """Test handling of ValueError during service calls."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock service call to raise ValueError
        hass.services.async_call.side_effect = ValueError("Invalid entity ID format")

        # Should raise ServiceCallError with specific error message
        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(MOCK_COVER_ENTITY_ID, 50, 15)

    @pytest.mark.asyncio
    async def test_service_call_type_error(self) -> None:
        """Test handling of TypeError during service calls."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock service call to raise TypeError
        hass.services.async_call.side_effect = TypeError("'NoneType' object is not callable")

        # Should raise ServiceCallError with specific error message
        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(MOCK_COVER_ENTITY_ID, 50, 15)

    @pytest.mark.asyncio
    async def test_service_call_unexpected_error(self) -> None:
        """Test handling of unexpected errors during service calls."""
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock service call to raise unexpected error
        hass.services.async_call.side_effect = RuntimeError("Network connection lost")

        # Should raise ServiceCallError with specific error message
        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(MOCK_COVER_ENTITY_ID, 50, 15)

    @pytest.mark.asyncio
    async def test_service_call_error_during_automation_update(self) -> None:
        """Test service call error handling during full automation update."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service
        async def mock_weather_service(domain, service, service_data, **kwargs):
            if domain == "weather":
                return {
                    "weather.forecast": {
                        "forecast": [
                            {
                                "datetime": "2023-01-01T12:00:00Z",
                                "native_temperature": 30.0,  # Hot temperature
                            }
                        ]
                    }
                }
            else:
                # Simulate cover service call failure
                raise ServiceNotFound("cover", "set_cover_position")

        hass.services.async_call.side_effect = mock_weather_service

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock weather and sun entities to trigger cover movement
        weather_state = MagicMock()
        weather_state.state = "sunny"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            MOCK_COVER_ENTITY_ID: MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Should complete automation update despite service call error
        await coordinator.async_refresh()
        result = coordinator.data

        # Should complete with empty covers result since the error prevents proper execution
        assert "covers" in result
        assert result["covers"] == {}

    @pytest.mark.asyncio
    async def test_weather_forecast_service_error(self) -> None:
        """Test handling of weather forecast service errors."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service to raise an error
        hass.services.async_call.side_effect = ServiceNotFound("weather", "get_forecasts")

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock entities to exist but weather service will fail
        weather_state = MagicMock()
        weather_state.state = "sunny"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            MOCK_COVER_ENTITY_ID: MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Should still complete update
        await coordinator.async_refresh()
        result = coordinator.data

        # Should have cover data
        assert "covers" in result

    @pytest.mark.asyncio
    async def test_weather_forecast_unexpected_error(self) -> None:
        """Test handling of unexpected errors during weather forecast retrieval."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service to raise unexpected error
        hass.services.async_call.side_effect = RuntimeError("Unexpected weather service error")

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock entities to exist but weather service will fail
        weather_state = MagicMock()
        weather_state.state = "sunny"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            MOCK_COVER_ENTITY_ID: MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Should still complete update
        await coordinator.async_refresh()
        result = coordinator.data

        # Should either return None or empty covers due to weather service error
        assert result is None or "covers" in result
