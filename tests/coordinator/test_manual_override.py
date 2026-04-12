"""Manual override detection tests.

This module contains comprehensive tests for the manual override detection logic
in the DataUpdateCoordinator, including timestamp handling, duration calculations,
and edge cases.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_CURRENT_TILT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.helpers import entity_registry as ha_entity_registry

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.cover_position_history import PositionEntry
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
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
        with patch.object(
            type(coordinator._automation_engine._cover_pos_history_mgr),
            "get_latest_entry",
            return_value=last_entry,
        ):
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

        # Mock the set_cover_position method to avoid actual service calls
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=0)  # Return target position

        with patch.object(
            type(coordinator._automation_engine._cover_pos_history_mgr),
            "get_latest_entry",
            return_value=last_entry,
        ):
            # Run automation
            result = await coordinator._async_update_data()

        # Verify target position was calculated (hot + sunny + sun hitting = close)
        cover_result = result.covers[MOCK_COVER_ENTITY_ID]
        assert cover_result.pos_target_desired is not None
        assert cover_result.pos_target_desired == 0  # Fully closed

    async def test_manual_override_expiry_logs_manual_override_end_reason(self, mock_hass: MagicMock) -> None:
        """Manual override expiry should emit the dedicated reopen reason in a full coordinator cycle."""

        mock_hass.config = MagicMock()
        mock_hass.config.language = "en"

        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800
        config_data[ConfKeys.AUTOMATIC_REOPENING_MODE.value] = const.ReopeningMode.ACTIVE.value
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        coordinator._ha_interface.set_cover_position = AsyncMock(side_effect=[0, 100])
        coordinator.status_sensor_unique_id = "test_unique_id"

        registry = MagicMock()
        integration_entity = MagicMock()
        integration_entity.unique_id = "test_unique_id"
        integration_entity.platform = const.DOMAIN
        integration_entity.entity_id = f"binary_sensor.{const.DOMAIN}_status"
        registry.entities = {"test_entity_registry_id": integration_entity}

        base_key = f"component.{const.DOMAIN}.{const.TRANSL_KEY_SERVICES}.{const.SERVICE_LOGBOOK_ENTRY}.{const.TRANSL_KEY_FIELDS}"
        translations = {
            f"{base_key}.{const.TRANSL_LOGBOOK_VERB_OPENING}.{const.TRANSL_ATTR_NAME}": "Opening",
            f"{base_key}.{const.TRANSL_LOGBOOK_VERB_CLOSING}.{const.TRANSL_ATTR_NAME}": "Closing",
            f"{base_key}.{const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION}.{const.TRANSL_ATTR_NAME}": "protect from heat",
            f"{base_key}.{const.TRANSL_LOGBOOK_REASON_END_MANUAL_OVERRIDE}.{const.TRANSL_ATTR_NAME}": "manual override ended",
            f"{base_key}.{const.TRANSL_LOGBOOK_TEMPLATE_COVER_MOVEMENT}.{const.TRANSL_ATTR_NAME}": "{verb} {entity_id} to {reason}. New position: {position}%.",
        }

        set_weather_forecast_temp(float(TEST_HOT_TEMP))
        state_mapping = create_combined_state_mock(
            sun_azimuth=180.0,
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: 100,
                    ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
                }
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        with (
            patch.object(ha_entity_registry, "async_get", return_value=registry),
            patch(
                "custom_components.smart_cover_automation.ha_interface.translation.async_get_translations",
                new_callable=AsyncMock,
                return_value=translations,
            ),
            patch("custom_components.smart_cover_automation.ha_interface.async_log_entry") as mock_log_entry,
        ):
            first_result = await coordinator._async_update_data()

            first_cover_result = first_result.covers[MOCK_COVER_ENTITY_ID]
            assert first_cover_result.pos_target_final == 0
            assert mock_log_entry.call_count == 1
            assert "protect from heat" in mock_log_entry.call_args.kwargs["message"]

            state_mapping[MOCK_COVER_ENTITY_ID].attributes = {
                ATTR_CURRENT_POSITION: 50,
                ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
            }

            second_result = await coordinator._async_update_data()

            second_cover_result = second_result.covers[MOCK_COVER_ENTITY_ID]
            assert second_cover_result.pos_target_desired is None
            assert coordinator._ha_interface.set_cover_position.await_count == 1

            latest_entry = coordinator._automation_engine._cover_pos_history_mgr.get_latest_entry(MOCK_COVER_ENTITY_ID)
            assert latest_entry is not None

            set_weather_forecast_temp(20.0)
            state_mapping[MOCK_SUN_ENTITY_ID].attributes = {"elevation": 45.0, "azimuth": 90.0}

            expired_time = latest_entry.timestamp + timedelta(seconds=1801)
            with patch("custom_components.smart_cover_automation.cover_automation.datetime") as mock_datetime:
                mock_datetime.now.return_value = expired_time
                mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                mock_datetime.timezone = timezone

                third_result = await coordinator._async_update_data()

            third_cover_result = third_result.covers[MOCK_COVER_ENTITY_ID]
            assert third_cover_result.pos_target_final == 100
            assert coordinator._ha_interface.set_cover_position.await_count == 2
            assert mock_log_entry.call_count == 2
            assert "manual override ended" in mock_log_entry.call_args.kwargs["message"]

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

        # Mock the set_cover_position method
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=0)

        with patch.object(
            type(coordinator._automation_engine._cover_pos_history_mgr),
            "get_latest_entry",
            return_value=last_entry,
        ):
            # Run automation
            result = await coordinator._async_update_data()

        # Verify automation proceeded normally
        cover_result = result.covers[MOCK_COVER_ENTITY_ID]
        assert cover_result.pos_target_desired is not None

    async def test_manual_override_ignores_small_post_tilt_position_drift(self, mock_hass: MagicMock) -> None:
        """Small position drift after automation tilt should not trigger manual override.

        Scenario:
        1. First coordinator cycle closes a tilt-capable cover and applies closed tilt.
        2. Second cycle reports the real device state as 2% open because tilt nudged the cover.

        Expected:
        - The second cycle should still evaluate automation normally.
        - No new manual override should be activated.
        - No extra position or tilt command should be sent for the 2% drift.
        """

        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800
        config_data[ConfKeys.TILT_MODE_DAY.value] = "closed"
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=0)
        coordinator._ha_interface.set_cover_tilt_position = AsyncMock(return_value=0)
        coordinator._ha_interface.add_logbook_entry = AsyncMock()

        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        tilt_features = int(CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION)
        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: 100,
                    ATTR_CURRENT_TILT_POSITION: 50,
                    ATTR_SUPPORTED_FEATURES: tilt_features,
                }
            }
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        first_result = await coordinator._async_update_data()

        first_cover_result = first_result.covers[MOCK_COVER_ENTITY_ID]
        assert first_cover_result.pos_target_desired == 0
        assert first_cover_result.pos_target_final == 0
        assert first_cover_result.tilt_target == 0
        assert coordinator._ha_interface.set_cover_position.await_count == 1
        assert coordinator._ha_interface.set_cover_tilt_position.await_count == 1

        state_mapping[MOCK_COVER_ENTITY_ID].attributes = {
            ATTR_CURRENT_POSITION: 2,
            ATTR_CURRENT_TILT_POSITION: 0,
            ATTR_SUPPORTED_FEATURES: tilt_features,
        }

        second_result = await coordinator._async_update_data()

        second_cover_result = second_result.covers[MOCK_COVER_ENTITY_ID]
        assert second_cover_result.pos_current == 2
        assert second_cover_result.pos_target_desired == 0
        assert second_cover_result.pos_target_final is None
        assert coordinator._ha_interface.set_cover_position.await_count == 1
        assert coordinator._ha_interface.set_cover_tilt_position.await_count == 1

        latest_entry = coordinator._automation_engine._cover_pos_history_mgr.get_latest_entry(MOCK_COVER_ENTITY_ID)
        assert latest_entry is not None
        assert latest_entry.position == 2

    async def test_manual_override_ignores_small_post_movement_position_drift(self, mock_hass: MagicMock) -> None:
        """Small position drift after automation movement should not trigger manual override.

        Scenario:
        1. First coordinator cycle opens a cover to 100%.
        2. Second cycle reports the real device state as 98% because the actuator or sensor is imprecise.

        Expected:
        - The second cycle should still evaluate automation normally.
        - No new manual override should be activated.
        - No extra position command should be sent for the 2% drift.
        """

        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800
        config_data[ConfKeys.AUTOMATIC_REOPENING_MODE.value] = const.ReopeningMode.ACTIVE.value
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=100)
        coordinator._ha_interface.add_logbook_entry = AsyncMock()

        set_weather_forecast_temp(20.0)

        state_mapping = create_combined_state_mock(
            sun_azimuth=90.0,
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: 0,
                    ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
                }
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        first_result = await coordinator._async_update_data()

        first_cover_result = first_result.covers[MOCK_COVER_ENTITY_ID]
        assert first_cover_result.pos_target_desired == 100
        assert first_cover_result.pos_target_final == 100
        assert coordinator._ha_interface.set_cover_position.await_count == 1

        state_mapping[MOCK_COVER_ENTITY_ID].attributes = {
            ATTR_CURRENT_POSITION: 98,
            ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
        }

        second_result = await coordinator._async_update_data()

        second_cover_result = second_result.covers[MOCK_COVER_ENTITY_ID]
        assert second_cover_result.pos_current == 98
        assert second_cover_result.pos_target_desired == 100
        assert second_cover_result.pos_target_final is None
        assert coordinator._ha_interface.set_cover_position.await_count == 1

        latest_entry = coordinator._automation_engine._cover_pos_history_mgr.get_latest_entry(MOCK_COVER_ENTITY_ID)
        assert latest_entry is not None
        assert latest_entry.position == 98

    async def test_manual_override_ignores_small_post_opening_drift_for_tilt_capable_cover(self, mock_hass: MagicMock) -> None:
        """Small opening drift should still be ignored for a tilt-capable cover.

        This pins down that the generalized settle tracker handles opening drift
        even when the cover supports tilt and no tilt command is sent at 100%.
        """

        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800
        config_data[ConfKeys.AUTOMATIC_REOPENING_MODE.value] = const.ReopeningMode.ACTIVE.value
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=100)
        coordinator._ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)
        coordinator._ha_interface.add_logbook_entry = AsyncMock()

        set_weather_forecast_temp(20.0)

        tilt_features = int(CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION)
        state_mapping = create_combined_state_mock(
            sun_azimuth=90.0,
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: 0,
                    ATTR_CURRENT_TILT_POSITION: 0,
                    ATTR_SUPPORTED_FEATURES: tilt_features,
                }
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        first_result = await coordinator._async_update_data()

        first_cover_result = first_result.covers[MOCK_COVER_ENTITY_ID]
        assert first_cover_result.pos_target_desired == 100
        assert first_cover_result.pos_target_final == 100
        assert coordinator._ha_interface.set_cover_position.await_count == 1
        assert coordinator._ha_interface.set_cover_tilt_position.await_count == 0

        state_mapping[MOCK_COVER_ENTITY_ID].attributes = {
            ATTR_CURRENT_POSITION: 98,
            ATTR_CURRENT_TILT_POSITION: 100,
            ATTR_SUPPORTED_FEATURES: tilt_features,
        }

        second_result = await coordinator._async_update_data()

        second_cover_result = second_result.covers[MOCK_COVER_ENTITY_ID]
        assert second_cover_result.pos_current == 98
        assert second_cover_result.pos_target_desired == 100
        assert second_cover_result.pos_target_final is None
        assert coordinator._ha_interface.set_cover_position.await_count == 1
        assert coordinator._ha_interface.set_cover_tilt_position.await_count == 0

    async def test_manual_override_does_not_ignore_drift_when_position_delta_is_zero(self, mock_hass: MagicMock) -> None:
        """Zero position tolerance should disable settle-drift acceptance."""

        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800
        config_data[ConfKeys.COVERS_MIN_POSITION_DELTA.value] = 0
        config_data[ConfKeys.AUTOMATIC_REOPENING_MODE.value] = const.ReopeningMode.ACTIVE.value
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=100)
        coordinator._ha_interface.add_logbook_entry = AsyncMock()

        set_weather_forecast_temp(20.0)

        state_mapping = create_combined_state_mock(
            sun_azimuth=90.0,
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: 0,
                    ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
                }
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator._async_update_data()

        state_mapping[MOCK_COVER_ENTITY_ID].attributes = {
            ATTR_CURRENT_POSITION: 98,
            ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
        }

        second_result = await coordinator._async_update_data()

        second_cover_result = second_result.covers[MOCK_COVER_ENTITY_ID]
        assert second_cover_result.pos_current == 98
        assert second_cover_result.pos_target_desired is None
        assert coordinator._ha_interface.set_cover_position.await_count == 1

    async def test_manual_override_resumes_after_settle_window_expires(self, mock_hass: MagicMock) -> None:
        """Small drift should stop being ignored once the settle window has expired."""

        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800
        config_data[ConfKeys.AUTOMATIC_REOPENING_MODE.value] = const.ReopeningMode.ACTIVE.value
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=100)
        coordinator._ha_interface.add_logbook_entry = AsyncMock()

        set_weather_forecast_temp(20.0)

        state_mapping = create_combined_state_mock(
            sun_azimuth=90.0,
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: 0,
                    ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
                }
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator._async_update_data()

        latest_entry = coordinator._automation_engine._cover_pos_history_mgr.get_latest_entry(MOCK_COVER_ENTITY_ID)
        assert latest_entry is not None

        state_mapping[MOCK_COVER_ENTITY_ID].attributes = {
            ATTR_CURRENT_POSITION: 98,
            ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
        }

        expired_time = latest_entry.timestamp + (const.UPDATE_INTERVAL * (const.COVER_AUTOMATION_SETTLE_CYCLES + 1))
        with patch("custom_components.smart_cover_automation.cover_automation.datetime") as mock_datetime:
            mock_datetime.now.return_value = expired_time
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            mock_datetime.timezone = timezone
            second_result = await coordinator._async_update_data()

        second_cover_result = second_result.covers[MOCK_COVER_ENTITY_ID]
        assert second_cover_result.pos_current == 98
        assert second_cover_result.pos_target_desired is None
        assert coordinator._ha_interface.set_cover_position.await_count == 1

    async def test_manual_override_detects_large_post_movement_drift(self, mock_hass: MagicMock) -> None:
        """Large drift after automation movement should still count as manual override."""

        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800
        config_data[ConfKeys.AUTOMATIC_REOPENING_MODE.value] = const.ReopeningMode.ACTIVE.value
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=100)
        coordinator._ha_interface.add_logbook_entry = AsyncMock()

        set_weather_forecast_temp(20.0)

        state_mapping = create_combined_state_mock(
            sun_azimuth=90.0,
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: 0,
                    ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
                }
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator._async_update_data()

        state_mapping[MOCK_COVER_ENTITY_ID].attributes = {
            ATTR_CURRENT_POSITION: 90,
            ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
        }

        second_result = await coordinator._async_update_data()

        second_cover_result = second_result.covers[MOCK_COVER_ENTITY_ID]
        assert second_cover_result.pos_current == 90
        assert second_cover_result.pos_target_desired is None
        assert coordinator._ha_interface.set_cover_position.await_count == 1

    async def test_manual_override_ignores_small_post_lock_movement_drift(self, mock_hass: MagicMock) -> None:
        """Small drift after lock-enforced movement should not trigger manual override.

        FORCE_OPEN should still re-issue the position command because lock enforcement
        requires the exact forced target, but the drift must not be treated as manual
        override before that happens.
        """

        config_data = create_sun_config()
        config_data[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800
        config_data[ConfKeys.LOCK_MODE.value] = "force_open"
        config_entry = MockConfigEntry(config_data)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        coordinator._ha_interface.set_cover_position = AsyncMock(return_value=100)
        coordinator._ha_interface.add_logbook_entry = AsyncMock()

        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: {
                    ATTR_CURRENT_POSITION: 0,
                    ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
                }
            }
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        first_result = await coordinator._async_update_data()

        first_cover_result = first_result.covers[MOCK_COVER_ENTITY_ID]
        assert first_cover_result.pos_target_final == 100
        assert coordinator._ha_interface.set_cover_position.await_count == 1

        state_mapping[MOCK_COVER_ENTITY_ID].attributes = {
            ATTR_CURRENT_POSITION: 98,
            ATTR_SUPPORTED_FEATURES: int(CoverEntityFeature.SET_POSITION),
        }

        second_result = await coordinator._async_update_data()

        second_cover_result = second_result.covers[MOCK_COVER_ENTITY_ID]
        assert second_cover_result.pos_current == 98
        assert second_cover_result.pos_target_final == 100
        assert coordinator._ha_interface.set_cover_position.await_count == 2
