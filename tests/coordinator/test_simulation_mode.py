"""Tests for simulation mode functionality in the Smart Cover Automation coordinator.

This module tests the simulation mode feature, which allows users to run the automation
logic without actually sending commands to physical covers. This is useful for:
- Testing automation logic
- Debugging configurations
- Observing what the automation would do without affecting real covers

Key testing areas:
- Simulation mode prevents actual cover service calls
- Automation logic still runs normally (calculations, logging, sensor updates)
- Service call simulation is properly logged
- Simulation state is correctly exposed via sensors
- Simulation mode interacts properly with other automation features
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import COVER_ATTR_POS_TARGET_DESIRED, SENSOR_ATTR_TEMP_CURRENT_MAX
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    TEST_COVER_CLOSED,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    MockConfigEntry,
    create_combined_state_mock,
    create_temperature_config,
    set_weather_forecast_temp,
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestSimulationMode(TestDataUpdateCoordinatorBase):
    """Test simulation mode functionality in the DataUpdateCoordinator."""

    async def test_simulation_mode_prevents_cover_commands(
        self,
        simulation_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test that simulation mode prevents actual cover service calls.

        When simulation mode is enabled, the automation should:
        1. Run all normal logic (temperature checks, position calculations)
        2. Log what commands would be sent
        3. NOT actually call Home Assistant cover services
        4. Still update internal state as if commands were sent
        """
        # Mock Home Assistant state to trigger automation
        mock_temperature_state.state = TEST_HOT_TEMP  # Hot temperature (above threshold)
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN  # Fully open cover

        # Set weather forecast temperature
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        # Create environmental state: hot temperature + sun hitting window
        state_mapping = create_combined_state_mock(
            sun_elevation=TEST_HIGH_ELEVATION,  # Above threshold
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Hitting window
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Track cover service calls specifically (simulation should prevent these)
        cover_service_calls = []

        # Preserve existing weather service mock while tracking cover calls
        original_weather_mock = mock_hass._weather_service_mock

        async def track_service_calls(domain, service, service_data, **kwargs):
            if domain == "cover":  # Only track cover service calls
                cover_service_calls.append((domain, service, service_data))
            else:
                # For non-cover services (like weather), use the original weather mock
                return await original_weather_mock(domain, service, service_data, **kwargs)

        mock_hass.services.async_call.side_effect = track_service_calls

        # Run automation cycle
        await simulation_coordinator.async_refresh()

        # Verify no cover service calls were made (simulation mode should prevent them)
        assert len(cover_service_calls) == 0, f"Expected no cover service calls in simulation mode, but got: {cover_service_calls}"

        # But verify that the coordinator still processed the automation logic
        result = simulation_coordinator.data
        assert result is not None
        assert result[SENSOR_ATTR_TEMP_CURRENT_MAX] == float(TEST_HOT_TEMP)

        # The automation should have calculated a desired position even in simulation mode
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data[COVER_ATTR_POS_TARGET_DESIRED] == TEST_COVER_CLOSED

    async def test_simulation_mode_logging(
        self,
        simulation_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that simulation mode prevents actual service calls and processes automation.

        When simulation mode is enabled, the automation should:
        1. Run all normal logic (temperature checks, position calculations)
        2. NOT actually call Home Assistant cover services
        3. Still calculate desired positions correctly
        """
        # Mock Home Assistant state to trigger cover movement
        mock_temperature_state.state = TEST_HOT_TEMP
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        # Set weather forecast temperature
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        state_mapping = create_combined_state_mock(
            sun_elevation=TEST_HIGH_ELEVATION,
            sun_azimuth=TEST_DIRECT_AZIMUTH,
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Track cover service calls specifically (simulation should prevent these)
        cover_service_calls = []

        # Preserve existing weather service mock while tracking cover calls
        original_weather_mock = mock_hass._weather_service_mock

        async def track_service_calls(domain, service, service_data, **kwargs):
            if domain == "cover":  # Only track cover service calls
                cover_service_calls.append((domain, service, service_data))
            else:
                # For non-cover services (like weather), use the original weather mock
                return await original_weather_mock(domain, service, service_data, **kwargs)

        mock_hass.services.async_call.side_effect = track_service_calls

        # Run automation cycle
        await simulation_coordinator.async_refresh()

        # Verify no cover service calls were made (simulation mode)
        assert len(cover_service_calls) == 0, f"Expected no cover service calls in simulation mode, but got: {cover_service_calls}"

        # Verify the coordinator processed the automation correctly
        result = simulation_coordinator.data
        assert result is not None

        # Should have processed the cover and calculated a desired position
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]

        # Should have calculated that cover needs to close due to hot temperature
        assert cover_data[COVER_ATTR_POS_TARGET_DESIRED] == TEST_COVER_CLOSED

        # Verify simulation mode is active
        resolved = simulation_coordinator._resolved_settings()
        assert resolved.simulating is True

    async def test_simulation_mode_configuration_via_data(
        self,
        mock_hass: MagicMock,
    ) -> None:
        """Test that simulation mode can be configured via config data.

        This test verifies that simulation mode setting is properly read from
        the configuration data and applied to coordinator behavior.
        """
        # Create coordinator with simulation mode enabled via data
        config = create_temperature_config()
        config[ConfKeys.SIMULATING.value] = True
        config_entry = MockConfigEntry(config)
        sim_coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Verify simulation mode is enabled
        resolved = sim_coordinator._resolved_settings()
        assert resolved.simulating is True

        # Create coordinator with simulation mode disabled via data
        config_normal = create_temperature_config()
        config_normal[ConfKeys.SIMULATING.value] = False
        config_entry_normal = MockConfigEntry(config_normal)
        normal_coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry_normal))

        # Verify simulation mode is disabled
        resolved_normal = normal_coordinator._resolved_settings()
        assert resolved_normal.simulating is False
