"""
Test cover control edge cases in the coordinator.

This module tests edge cases in cover control logic including
position delta handling and error scenarios.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

from custom_components.smart_cover_automation.const import COVER_ATTR_POS_TARGET_DESIRED
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from ..conftest import (
    MockConfigEntry,
    create_mock_weather_service,
    create_temperature_config,
    set_weather_forecast_temp,
)


class TestCoverControlEdgeCases:
    """Test cover control edge cases."""

    async def test_minor_position_adjustment_skipped(self) -> None:
        """Test that minor position adjustments are skipped based on min_position_delta."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service
        set_weather_forecast_temp(30.0)  # Hot temperature
        hass.services.async_call.side_effect = create_mock_weather_service()

        # Create config with min_position_delta of 10
        config = create_temperature_config()
        config["covers_min_position_delta"] = 10
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock weather and sun entities to trigger cover closing
        weather_state = MagicMock()
        weather_state.state = "sunny"

        # Cover is already at position 5, should close to 0, but difference is only 5 < 10
        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test_cover": MagicMock(attributes={"current_position": 5, "supported_features": 15}),
        }.get(entity_id)

        await coordinator.async_refresh()

        # Should not make any cover service calls due to minor adjustment
        cover_calls = [call for call in hass.services.async_call.call_args_list if call[0][0] == "cover"]
        assert len(cover_calls) == 0

    async def test_exact_position_no_movement_needed(self) -> None:
        """Test that no movement is made when cover is already at desired position."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service
        set_weather_forecast_temp(30.0)  # Hot temperature
        hass.services.async_call.side_effect = create_mock_weather_service()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock weather and sun entities to trigger cover closing
        weather_state = MagicMock()
        weather_state.state = "sunny"

        # Cover is already at position 0 (fully closed), which is the desired position
        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test_cover": MagicMock(attributes={"current_position": 0, "supported_features": 15}),
        }.get(entity_id)

        await coordinator.async_refresh()

        # Should not make any cover service calls since no movement needed
        cover_calls = [call for call in hass.services.async_call.call_args_list if call[0][0] == "cover"]
        assert len(cover_calls) == 0

    def test_calculate_angle_difference_edge_cases(self) -> None:
        """Test angle difference calculation with edge cases."""
        from custom_components.smart_cover_automation.automation_engine import CoverAutomation

        # Test exact same angles
        diff = CoverAutomation._calculate_angle_difference(180.0, 180.0)
        assert diff == 0.0

        # Test angles crossing 0/360 boundary
        diff = CoverAutomation._calculate_angle_difference(10.0, 350.0)
        assert diff == 20.0

        # Test maximum difference (180 degrees)
        diff = CoverAutomation._calculate_angle_difference(0.0, 180.0)
        assert diff == 180.0

        # Test with negative angles (should still work)
        diff = CoverAutomation._calculate_angle_difference(-10.0, 10.0)
        assert diff == 20.0

        # Test with angles > 360
        diff = CoverAutomation._calculate_angle_difference(450.0, 90.0)
        assert diff == 0.0  # 450 % 360 = 90

    async def test_cover_debug_logging_paths(self) -> None:
        """Test debug logging paths in cover evaluation."""
        hass = MagicMock()
        hass.services = MagicMock()
        hass.states = MagicMock()

        # Mock weather forecast service
        set_weather_forecast_temp(15.0)  # Cold temperature
        hass.services.async_call.side_effect = create_mock_weather_service()

        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Mock weather and sun entities for cold weather (covers should open)
        weather_state = MagicMock()
        weather_state.state = "sunny"

        hass.states.get.side_effect = lambda entity_id: {
            "weather.forecast": weather_state,
            "sun.sun": MagicMock(state="above_horizon", attributes={"elevation": 45, "azimuth": 180}),
            "cover.test_cover": MagicMock(attributes={"current_position": 0, "supported_features": 15}),
        }.get(entity_id)

        # This should trigger the debug logging path where covers open due to cold weather
        await coordinator.async_refresh()
        result = coordinator.data

        # Should have processed the cover
        assert "covers" in result
        assert "cover.test_cover" in result["covers"]
        cover_data = result["covers"]["cover.test_cover"]
        assert cover_data[COVER_ATTR_POS_TARGET_DESIRED] == 100  # Should open due to cold
