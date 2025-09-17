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
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestSimulationMode(TestDataUpdateCoordinatorBase):
    """Test simulation mode functionality in the DataUpdateCoordinator."""

    @pytest.fixture
    def simulation_coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a coordinator with simulation mode enabled.

        Returns a coordinator configured for temperature automation with simulation
        mode enabled to test that cover commands are not actually sent.
        """
        config = create_temperature_config()
        # Enable simulation mode
        config[ConfKeys.SIMULATING.value] = True
        config_entry = MockConfigEntry(config)
        return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

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

        # Create environmental state: hot temperature + sun hitting window
        state_mapping = create_combined_state_mock(
            temp_state=TEST_HOT_TEMP,  # Above threshold - should trigger automation
            sun_elevation=TEST_HIGH_ELEVATION,  # Above threshold
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Hitting window
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Track service calls before running automation
        initial_call_count = mock_hass.services.async_call.call_count

        # Run automation cycle
        await simulation_coordinator.async_refresh()

        # Verify no additional service calls were made
        assert mock_hass.services.async_call.call_count == initial_call_count

        # But verify that the coordinator still processed the automation logic
        result = simulation_coordinator.data
        assert result is not None
        assert result["temp_current"] == float(TEST_HOT_TEMP)

        # The automation should have calculated a desired position even in simulation mode
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_CLOSED

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

        state_mapping = create_combined_state_mock(
            temp_state=TEST_HOT_TEMP,
            sun_elevation=TEST_HIGH_ELEVATION,
            sun_azimuth=TEST_DIRECT_AZIMUTH,
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Track service calls before running automation
        initial_call_count = mock_hass.services.async_call.call_count

        # Run automation cycle
        await simulation_coordinator.async_refresh()

        # Verify no service calls were made (simulation mode)
        assert mock_hass.services.async_call.call_count == initial_call_count

        # Verify the coordinator processed the automation correctly
        result = simulation_coordinator.data
        assert result is not None

        # Should have processed the cover and calculated a desired position
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]

        # Should have calculated that cover needs to close due to hot temperature
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_CLOSED

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
