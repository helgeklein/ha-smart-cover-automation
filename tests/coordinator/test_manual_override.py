"""Manual override detection tests.

This module contains comprehensive tests for the manual override detection logic
in the DataUpdateCoordinator, including timestamp handling, duration calculations,
and edge cases.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_ATTR_MESSAGE,
    COVER_ATTR_POS_CURRENT,
    COVER_ATTR_POS_TARGET_DESIRED,
)
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
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)

        # Run automation
        result = await coordinator._async_update_data()

        # Verify manual override was detected
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert COVER_ATTR_MESSAGE in cover_result
        assert "Manual override detected" in cover_result[COVER_ATTR_MESSAGE]
        assert "skipping this cover for another" in cover_result[COVER_ATTR_MESSAGE]

        # Verify current position is recorded but no target position is set
        assert cover_result[COVER_ATTR_POS_CURRENT] == current_position
        assert COVER_ATTR_POS_TARGET_DESIRED not in cover_result

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
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)

        # Mock the set_cover_position method to avoid actual service calls
        coordinator._set_cover_position = AsyncMock(return_value=0)  # Return target position

        # Run automation
        result = await coordinator._async_update_data()

        # Verify automation proceeded normally (no manual override message)
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        message = cover_result.get(COVER_ATTR_MESSAGE, "")
        assert "Manual override detected" not in message

        # Verify target position was calculated (hot + sunny + sun hitting = close)
        assert COVER_ATTR_POS_TARGET_DESIRED in cover_result
        assert cover_result[COVER_ATTR_POS_TARGET_DESIRED] == 0  # Fully closed

    async def test_manual_override_custom_duration(self, mock_hass: MagicMock) -> None:
        """Test manual override with custom duration setting.

        Scenario: Custom 10-minute override duration, position changed 5 minutes ago
        Expected: Manual override should still be active
        """
        # Setup configuration with custom 10-minute override duration
        custom_duration = 600  # 10 minutes in seconds
        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = custom_duration
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        # Create cover state
        current_position = 100
        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: current_position,
                    ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
                }
            }
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Mock position history: position changed 5 minutes ago (within custom 10-minute override)
        last_entry = self._create_position_history_entry(position=75, minutes_ago=5)
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)

        # Run automation
        result = await coordinator._async_update_data()

        # Verify manual override is still active
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert "Manual override detected" in cover_result[COVER_ATTR_MESSAGE]
        assert "skipping this cover for another" in cover_result[COVER_ATTR_MESSAGE]

    async def test_manual_override_custom_duration_expired(self, mock_hass: MagicMock) -> None:
        """Test manual override with custom duration that has expired.

        Scenario: Custom 10-minute override duration, position changed 15 minutes ago
        Expected: Manual override should be expired, automation proceeds
        """
        # Setup configuration with custom 10-minute override duration
        custom_duration = 600  # 10 minutes in seconds
        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = custom_duration
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        # Create cover state
        current_position = 100
        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: current_position,
                    ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
                }
            }
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Mock position history: position changed 15 minutes ago (beyond custom 10-minute override)
        last_entry = self._create_position_history_entry(position=75, minutes_ago=15)
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)

        # Mock the set_cover_position method
        coordinator._set_cover_position = AsyncMock(return_value=0)

        # Run automation
        result = await coordinator._async_update_data()

        # Verify automation proceeded (override expired)
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        message = cover_result.get(COVER_ATTR_MESSAGE, "")
        assert "Manual override detected" not in message

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
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)

        # Mock the set_cover_position method
        coordinator._set_cover_position = AsyncMock(return_value=0)

        # Run automation
        result = await coordinator._async_update_data()

        # Verify no manual override was detected
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        message = cover_result.get(COVER_ATTR_MESSAGE, "")
        assert "Manual override detected" not in message

        # Verify automation proceeded normally
        assert COVER_ATTR_POS_TARGET_DESIRED in cover_result

    async def test_no_manual_override_no_history(self, mock_hass: MagicMock) -> None:
        """Test that no manual override when there's no position history.

        Scenario: No previous position history exists for the cover
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

        # Mock position history: no history exists
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=None)

        # Mock the set_cover_position method
        coordinator._set_cover_position = AsyncMock(return_value=0)

        # Run automation
        result = await coordinator._async_update_data()

        # Verify no manual override was detected
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        message = cover_result.get(COVER_ATTR_MESSAGE, "")
        assert "Manual override detected" not in message

    async def test_manual_override_time_boundary_cases(self, mock_hass: MagicMock) -> None:
        """Test manual override detection at exact time boundaries.

        Tests edge cases around the exact override duration boundary.
        """
        # Test case 1: Exactly at the boundary (should not trigger override)
        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800  # 30 minutes
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

        # Mock position history: exactly 30 minutes ago (at boundary)
        last_entry = self._create_position_history_entry(position=50, minutes_ago=30)
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)
        coordinator._set_cover_position = AsyncMock(return_value=0)

        # Run automation
        result = await coordinator._async_update_data()

        # At exactly the boundary, override should be expired
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        message = cover_result.get(COVER_ATTR_MESSAGE, "")
        assert "Manual override detected" not in message

    async def test_manual_override_system_time_edge_case(self, mock_hass: MagicMock) -> None:
        """Test manual override handles system time changes gracefully.

        Scenario: History timestamp is in the future (system time was changed)
        Expected: Override should not be triggered to avoid weird behavior
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

        # Mock position history: timestamp in the future (system time was changed backwards)
        future_timestamp = datetime.now(timezone.utc) + timedelta(minutes=10)
        last_entry = PositionEntry(position=50, cover_moved=True, timestamp=future_timestamp)
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)
        coordinator._set_cover_position = AsyncMock(return_value=0)

        # Run automation
        result = await coordinator._async_update_data()

        # Should not trigger override when timestamp is in future
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        message = cover_result.get(COVER_ATTR_MESSAGE, "")
        assert "Manual override detected" not in message

    async def test_manual_override_duration_calculation_accuracy(self, mock_hass: MagicMock) -> None:
        """Test that the remaining time calculation in override message is accurate.

        Verifies that the time_remaining calculation in the override message is correct.
        """
        # Use a custom short duration for precise testing
        override_duration = 300  # 5 minutes
        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = override_duration
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

        # Mock position history: 2 minutes ago (3 minutes remaining)
        minutes_elapsed = 2
        expected_remaining = override_duration - (minutes_elapsed * 60)  # 180 seconds

        last_entry = self._create_position_history_entry(position=50, minutes_ago=minutes_elapsed)
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)

        # Run automation
        result = await coordinator._async_update_data()

        # Verify the remaining time in the message is approximately correct
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        message = cover_result[COVER_ATTR_MESSAGE]

        # Extract the remaining time from the message (format: "another X s")
        import re

        match = re.search(r"another (\d+(?:\.\d+)?) s", message)
        assert match is not None, f"Could not find remaining time in message: {message}"

        remaining_time = float(match.group(1))
        # Allow some tolerance for test execution time (within 5 seconds)
        assert abs(remaining_time - expected_remaining) < 5, f"Expected ~{expected_remaining}s, got {remaining_time}s"

    @pytest.mark.parametrize(
        "position_change,minutes_ago,override_duration_minutes,should_override,test_description",
        [
            (25, 5, 30, True, "Recent change within override period"),
            (50, 35, 30, False, "Old change beyond override period"),
            (50, 8, 10, True, "Recent change within custom short period"),  # Changed from 75 to 50
            (100, 12, 10, False, "Old change beyond custom short period"),
            (25, 29, 30, True, "Change just within override period"),
            (25, 31, 30, False, "Change just beyond override period"),
        ],
    )
    async def test_manual_override_parametrized_scenarios(
        self,
        mock_hass: MagicMock,
        position_change: int,
        minutes_ago: int,
        override_duration_minutes: int,
        should_override: bool,
        test_description: str,
    ) -> None:
        """Test various manual override scenarios with different timings and durations."""
        override_duration_seconds = override_duration_minutes * 60

        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = override_duration_seconds
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

        # Mock position history with the specified change
        last_entry = self._create_position_history_entry(position=position_change, minutes_ago=minutes_ago)
        coordinator._cover_pos_history_mgr.get_latest_entry = MagicMock(return_value=last_entry)
        coordinator._set_cover_position = AsyncMock(return_value=0)

        # Run automation
        result = await coordinator._async_update_data()

        # Verify override behavior matches expectation
        cover_result = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        message = cover_result.get(COVER_ATTR_MESSAGE, "")

        if should_override:
            assert "Manual override detected" in message, f"Expected override for: {test_description}"
            assert COVER_ATTR_POS_TARGET_DESIRED not in cover_result, f"Should not have target position during override: {test_description}"
        else:
            assert "Manual override detected" not in message, f"Should not override for: {test_description}"
            assert COVER_ATTR_POS_TARGET_DESIRED in cover_result, f"Should have target position when not overridden: {test_description}"
