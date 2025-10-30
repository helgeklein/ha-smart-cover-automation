"""Integration tests for coordinator's use of ha_interface.set_cover_position.

This module contains integration tests that verify the coordinator properly
initializes and uses the HA interface layer. Detailed unit tests for
set_cover_position functionality are in tests/ha_interface/test_ha_interface.py.

These integration tests focus on verifying that:
1. The coordinator correctly initializes the HA interface
2. The coordinator can successfully call set_cover_position through the interface
3. Configuration options (like simulation mode) are properly passed through
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

from homeassistant.components.cover import ATTR_POSITION, CoverEntityFeature
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    Platform,
)

from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from ..conftest import MockConfigEntry, create_temperature_config


#
# TestSetCoverPositionIntegration
#
class TestSetCoverPositionIntegration:
    """Integration tests for coordinator using HA interface to set cover positions."""

    #
    # test_coordinator_with_position_supporting_cover
    #
    async def test_coordinator_with_position_supporting_cover(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test that coordinator can control position-supporting covers through HA interface."""

        entity_id = "cover.test"
        desired_pos = 75
        features = CoverEntityFeature.SET_POSITION

        result = await coordinator._ha_interface.set_cover_position(entity_id, desired_pos, features)

        # Verify service was called correctly
        mock_hass.services.async_call.assert_called_once_with(
            Platform.COVER, SERVICE_SET_COVER_POSITION, {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: desired_pos}
        )

        # Verify return value
        assert result == desired_pos

    #
    # test_coordinator_with_binary_cover
    #
    async def test_coordinator_with_binary_cover(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test that coordinator can control binary covers (open/close only) through HA interface."""

        entity_id = "cover.test"
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        # Test open (above 50% threshold)
        result = await coordinator._ha_interface.set_cover_position(entity_id, 75, features)
        mock_hass.services.async_call.assert_called_with(Platform.COVER, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id})
        assert result == 100

        mock_hass.services.async_call.reset_mock()

        # Test close (at or below 50% threshold)
        result = await coordinator._ha_interface.set_cover_position(entity_id, 25, features)
        mock_hass.services.async_call.assert_called_with(Platform.COVER, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: entity_id})
        assert result == 0

    #
    # test_coordinator_with_simulation_mode
    #
    async def test_coordinator_with_simulation_mode(self, mock_hass: MagicMock) -> None:
        """Test that coordinator respects simulation mode configuration."""

        # Create coordinator with simulation mode enabled
        config = create_temperature_config()
        config["simulation_mode"] = True
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        entity_id = "cover.test"
        desired_pos = 75
        features = CoverEntityFeature.SET_POSITION

        # Execute
        result = await coordinator._ha_interface.set_cover_position(entity_id, desired_pos, features)

        # Verify no service call was made in simulation mode
        mock_hass.services.async_call.assert_not_called()

        # But return value should still be correct
        assert result == desired_pos
