"""Extra coordinator tests."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import (
    DataUpdateCoordinator,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MockConfigEntry,
    assert_service_called,
    create_combined_state_mock,
    create_temperature_config,
)

# Test constants
HOT_TEMP = "26.0"
COLD_TEMP = "18.0"
OPEN_POSITION = 100
CLOSED_POSITION = 0


class TestCoordinatorExtra:
    """Extra coordinator tests for edge cases."""

    @pytest.fixture
    def coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create coordinator for testing."""
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        return coordinator

    async def test_temperature_with_cold_trigger(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test temperature automation with cold trigger in combined mode."""
        # Temperature below minimum threshold to trigger opening
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: CLOSED_POSITION,
            "supported_features": CoverEntityFeature.SET_POSITION,
        }

        # Setup combined state for cold temp + sun not hitting
        state_mapping = create_combined_state_mock(
            temp_state=COLD_TEMP,  # Cold temp wants open
            sun_elevation=30.0,  # Above threshold but...
            sun_azimuth=90.0,  # Not hitting south-facing window
            cover_states={
                MOCK_COVER_ENTITY_ID: cover_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify - should open due to cold temp OR sun not hitting
        assert result is not None
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result["temp_current"] == float(COLD_TEMP)
        assert cover_data["sca_cover_desired_position"] == OPEN_POSITION

        # Verify service call
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=OPEN_POSITION,
        )

    async def test_combined_logic_comfortable_temp(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test combined logic with comfortable temperature."""
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: OPEN_POSITION,
            "supported_features": CoverEntityFeature.SET_POSITION,
        }

        # Setup comfortable temp + sun hitting - should stay open (neither condition for close/open)
        state_mapping = create_combined_state_mock(
            temp_state="22.0",  # Comfortable temp
            sun_elevation=30.0,  # Sun above threshold
            sun_azimuth=180.0,  # Sun hitting window
            cover_states={
                MOCK_COVER_ENTITY_ID: cover_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify - should maintain current position
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == OPEN_POSITION  # No change

        # Verify no service call
        mock_hass.services.async_call.assert_not_called()
