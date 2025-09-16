"""Additional coordinator tests for complex automation scenarios.

This module contains supplementary tests for the DataUpdateCoordinator that focus on
specific edge cases and complex automation logic not covered in the main coordinator
test suite. These tests verify:

- Combined temperature and sun automation behavior in edge conditions
- Cold temperature trigger scenarios with various sun positions
- Comfortable temperature handling when neither open nor close conditions are met
- Complex state interactions between temperature thresholds and sun positioning
- Service call verification for nuanced automation decisions

The tests use predefined temperature constants and cover position values to ensure
consistent testing of automation logic across different environmental conditions.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import (
    DataUpdateCoordinator,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COMFORTABLE_TEMP_1,
    TEST_COVER_CLOSED,
    TEST_COVER_OPEN,
    MockConfigEntry,
    assert_service_called,
    create_combined_state_mock,
    create_temperature_config,
)

# Test constants are now imported from conftest.py - see imports above for:
# TEST_HOT_TEMP, TEST_COLD_TEMP, TEST_COVER_OPEN, TEST_COVER_CLOSED


class TestCoordinatorExtra:
    """Additional test cases for DataUpdateCoordinator automation logic.

    This test class focuses on specific edge cases and complex scenarios that
    complement the main coordinator test suite. The tests verify:

    - Cold temperature automation triggers (opening covers for warmth)
    - Combined automation logic with comfortable temperatures
    - Complex interactions between temperature and sun position
    - Service call verification for nuanced automation decisions
    - Edge cases where no automation action should be taken

    These tests use realistic temperature values and sun positions to ensure
    the automation behaves correctly in real-world scenarios.
    """

    @pytest.fixture
    def coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a DataUpdateCoordinator instance configured for temperature automation testing.

        Sets up a coordinator with a temperature-based configuration using the
        mock Home Assistant instance. The coordinator is configured with:
        - Temperature automation enabled
        - Default temperature thresholds for hot/cold detection
        - Mock cover entities for testing automation actions

        Returns:
            DataUpdateCoordinator: Configured coordinator instance for testing
        """
        # Create config entry with temperature automation settings
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        return coordinator

    async def test_temperature_with_cold_trigger(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test cold temperature automation trigger in combined temperature/sun mode.

        Validates that the automation correctly opens covers when the temperature
        falls below the minimum threshold, even when sun conditions might otherwise
        suggest keeping covers closed. This test simulates a cold day where covers
        should open to allow warming sunlight into the room.

        Test scenario:
        - Temperature: 18°C (below threshold, triggers opening for warmth)
        - Sun elevation: 30° (above threshold but not the deciding factor)
        - Sun azimuth: 90° (not hitting south-facing window)
        - Current cover position: Closed (0)
        - Expected action: Open covers to 100 for warmth
        """
        # Setup cover in closed position with position control capability
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_CLOSED,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        # Create environmental state: cold temperature + sun not hitting window
        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp wants open
            sun_elevation=30.0,  # Above threshold but...
            sun_azimuth=90.0,  # Not hitting south-facing window
            cover_states={
                MOCK_COVER_ENTITY_ID: cover_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute automation logic
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify automation opens covers due to cold temperature
        assert result is not None
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result["temp_current"] == float(TEST_COLD_TEMP)
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN

        # Verify Home Assistant service call to open covers
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=TEST_COVER_OPEN,
        )

    async def test_combined_logic_comfortable_temp(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test combined automation logic with comfortable temperature conditions.

        Validates that the automation correctly maintains current cover positions
        when the temperature is in the comfortable range (neither too hot nor too cold)
        and no action is needed based on sun conditions. This test ensures the
        automation doesn't make unnecessary adjustments when conditions are optimal.

        Test scenario:
        - Temperature: 22°C (comfortable, no temperature-based action needed)
        - Sun elevation: 30° (above threshold)
        - Sun azimuth: 180° (hitting south-facing window)
        - Current cover position: Open (100)
        - Expected action: No change (maintain current position)
        """
        # Setup cover in open position with position control capability
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        # Create environmental state: comfortable temp + sun hitting window
        state_mapping = create_combined_state_mock(
            temp_state=TEST_COMFORTABLE_TEMP_1,  # Comfortable temp
            sun_elevation=30.0,  # Sun above threshold
            sun_azimuth=180.0,  # Sun hitting window
            cover_states={
                MOCK_COVER_ENTITY_ID: cover_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute automation logic
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify automation maintains current position (no action needed)
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN  # No change

        # Verify no Home Assistant service calls are made
        mock_hass.services.async_call.assert_not_called()
