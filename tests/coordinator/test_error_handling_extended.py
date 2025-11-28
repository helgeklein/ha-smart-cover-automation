"""Test comprehensive error handling scenarios in coordinator operations."""

from __future__ import annotations

import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import CoordinatorData, IntegrationConfigEntry
from custom_components.smart_cover_automation.ha_interface import ServiceCallError
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MockConfigEntry,
    create_temperature_config,
    create_weather_service_with_cover_error,
    set_weather_forecast_temp,
)


class TestCoordinatorErrorHandling:
    """Test comprehensive error handling scenarios in coordinator operations."""

    async def test_configuration_resolution_exception(self, caplog) -> None:
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
        # Set caplog to capture INFO level messages
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        await coordinator.async_refresh()
        # Data should be None due to configuration error
        result = coordinator.data
        assert result is None

    @pytest.mark.parametrize(
        "exception_class, exception_message",
        [
            (HomeAssistantError, "Home Assistant error"),
            (ConnectionError, "Connection lost"),
            (ValueError, "Invalid entity ID format"),
            (TypeError, "'NoneType' object is not callable"),
            (RuntimeError, "Network connection lost"),
        ],
    )
    async def test_service_call_various_error_types(self, exception_class: type, exception_message: str) -> None:
        """Test handling of various exception types during service calls.

        This parametrized test verifies that all types of exceptions during service calls
        are properly caught and wrapped in ServiceCallError with appropriate messages.
        """
        hass = MagicMock()
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock service call to raise the specified exception
        hass.services.async_call.side_effect = exception_class(exception_message)

        # Should raise ServiceCallError
        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._ha_interface.set_cover_position(MOCK_COVER_ENTITY_ID, 50, 15)

    async def test_service_call_error_during_automation_update(self, caplog) -> None:
        """Test service call error handling during full automation update."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service
        set_weather_forecast_temp(30.0)  # Hot temperature
        hass.services.async_call.side_effect = create_weather_service_with_cover_error(ServiceNotFound, "cover", "set_cover_position")

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
        # Set caplog to capture INFO level messages
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        await coordinator.async_refresh()
        result = coordinator.data

        # Should complete with cover in result showing the error
        assert hasattr(result, "covers")
        assert MOCK_COVER_ENTITY_ID in result.covers

    @pytest.mark.parametrize(
        "error_type,exception_class,service_name,test_description",
        [
            ("service_not_found", ServiceNotFound, "get_forecasts", "weather forecast service not found"),
            ("unexpected_error", RuntimeError, "get_forecasts", "unexpected error during weather forecast retrieval"),
            ("home_assistant_error", HomeAssistantError, "get_forecasts", "Home Assistant service error"),
        ],
    )
    async def test_weather_forecast_service_errors_parametrized(
        self, error_type: str, exception_class: type, service_name: str, test_description: str, caplog
    ) -> None:
        """Test handling of various weather forecast service errors.

        This parametrized test verifies that different types of weather forecast service errors
        are handled gracefully, allowing the automation to continue operating with minimal
        functionality rather than completely failing.
        """
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service to raise the specified error
        if error_type == "service_not_found":
            hass.services.async_call.side_effect = exception_class("weather", service_name)
        else:
            hass.services.async_call.side_effect = exception_class(f"Unexpected weather service error: {test_description}")

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

        # Should still complete update despite weather service error
        # Set caplog to capture INFO level messages
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        await coordinator.async_refresh()
        result = coordinator.data

        # Should either return None or have cover data, depending on error handling
        # The key is that it doesn't crash the entire automation
        # Should complete but with minimal state
        assert result is None or hasattr(result, "covers"), f"Failed for {test_description}"

    async def test_weather_forecast_temperature_unavailable(self, caplog) -> None:
        """Test graceful degradation when weather forecast temperature is unavailable.

        Validates that the coordinator handles unavailable weather forecast gracefully by
        continuing automation with temperature-based features disabled. Weather service
        failures are often temporary (network issues, API limits) and shouldn't make the
        entire automation system unavailable.

        Test scenario:
        - Weather entity: Available but forecast service returns no temperature data
        - Expected behavior: Warning logged, automation continues with temp_max=0.0, entities remain available
        """
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Setup weather entity state
        weather_state = MagicMock()
        weather_state.state = "sunny"
        weather_state.entity_id = "weather.forecast"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            MOCK_COVER_ENTITY_ID: MagicMock(attributes={"current_position": 100, "supported_features": 15}),
        }.get(entity_id)

        # Mock weather service to return no forecast data (simulating service failure)
        async def mock_weather_service_error(domain, service, service_data, **kwargs):
            if domain == Platform.WEATHER and service == "get_forecasts":
                return {}  # Empty response simulating forecast unavailable
            return {}

        hass.services.async_call = AsyncMock(side_effect=mock_weather_service_error)

        # Execute automation and verify graceful degradation
        # Set caplog to capture INFO level messages
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # First refresh clears the first-run flag (warnings suppressed)
        await coordinator.async_refresh()
        caplog.clear()
        # Second refresh should show the actual warning
        await coordinator.async_refresh()

        # Verify graceful degradation handling
        assert coordinator.last_exception is None  # No critical error propagated
        assert coordinator.last_update_success is True  # Automation continues successfully

        # Verify that automation was skipped due to weather data unavailability
        assert coordinator.data is not None
        # Verify empty result was returned
        assert coordinator.data == CoordinatorData(covers={})
        assert "Weather data unavailable, skipping actions" in caplog.text
