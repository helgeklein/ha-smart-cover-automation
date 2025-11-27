"""Manual override detection tests.

This module contains comprehensive tests for the manual override detection logic
in the DataUpdateCoordinator, including timestamp handling, duration calculations,
and edge cases.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.cover_position_history import PositionEntry
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    TEST_HOT_TEMP,
    MockConfigEntry,
    create_combined_state_mock,
    create_sun_config,
    set_weather_forecast_temp,
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestManualOverride(TestDataUpdateCoordinatorBase):
    """Test suite for manual override detection logic."""

    def _create_position_history_entry(self, position: int, minutes_ago: int, cover_moved: bool = True) -> PositionEntry:
        """Create a position entry with a timestamp in the past."""
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        return PositionEntry(position=position, cover_moved=cover_moved, timestamp=timestamp)

    async def test_manual_override_detection_recent_change(self, mock_hass: MagicMock) -> None:
        """Test that manual override is detected when position changed recently.

        Scenario: Cover position changed 10 minutes ago (within 30-minute default override duration)
        Expected: Automation should be skipped with manual override message
        """
        # Setup configuration with default manual override duration (1800 seconds = 30 minutes)
        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800  # 30 minutes
        config_entry = MockConfigEntry(config_data)

        # Create coordinator
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Set up weather forecast
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        # Create cover state with current position of 75%
        current_position = 75
        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: current_position,
                    ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
                }
            }
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(
            entity_id
        )  # Mock position history: last recorded position was 50% (different from current 75%)
        # and it was recorded 10 minutes ago (within override period)
        last_entry = self._create_position_history_entry(position=50, minutes_ago=10)
        coordinator._automation_engine._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)

        # Run automation
        result = await coordinator._async_update_data()

        # Verify current position is recorded but no target position is set
        cover_result = result.covers[MOCK_COVER_ENTITY_ID]
        assert cover_result.pos_current == current_position
        assert cover_result.pos_target_desired is None

    async def test_manual_override_expired_change(self, mock_hass: MagicMock) -> None:
        """Test that manual override expires after the configured duration.

        Scenario: Cover position changed 40 minutes ago (beyond 30-minute default override duration)
        Expected: Automation should proceed normally
        """
        # Setup configuration
        config_data = create_sun_config()
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        # Create cover state
        current_position = 75
        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: current_position,
                    ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
                }
            }
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Mock position history: position changed 40 minutes ago (beyond override period)
        last_entry = self._create_position_history_entry(position=50, minutes_ago=40)
        coordinator._automation_engine._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)

        # Mock the set_cover_position method to avoid actual service calls
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=0)  # Return target position

        # Run automation
        result = await coordinator._async_update_data()

        # Verify target position was calculated (hot + sunny + sun hitting = close)
        cover_result = result.covers[MOCK_COVER_ENTITY_ID]
        assert cover_result.pos_target_desired is not None
        assert cover_result.pos_target_desired == 0  # Fully closed

    async def test_no_manual_override_same_position(self, mock_hass: MagicMock) -> None:
        """Test that no manual override is detected when position hasn't changed.

        Scenario: Current position matches last recorded position
        Expected: No manual override, automation proceeds normally
        """
        config_data = create_sun_config()
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        # Create cover state
        current_position = 75
        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: current_position,
                    ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
                }
            }
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Mock position history: same position as current (no change)
        last_entry = self._create_position_history_entry(position=current_position, minutes_ago=5, cover_moved=False)
        coordinator._automation_engine._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)

        # Mock the set_cover_position method
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=0)

        # Run automation
        result = await coordinator._async_update_data()

        # Verify automation proceeded normally
        cover_result = result.covers[MOCK_COVER_ENTITY_ID]
        assert cover_result.pos_target_desired is not None
