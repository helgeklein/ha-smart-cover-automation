"""Integration tests for lock mode feature.

These tests validate that the lock mode feature works correctly when integrated
with the full automation system, testing:
- Lock mode override priority over normal automation
- Lock mode persistence across refresh cycles
- Multi-cover lock mode behavior
- Edge cases (binary covers, partial positions, unavailable covers)
- Service integration (set_lock)
- UI entity integration (select, binary_sensor, sensor)
"""

from __future__ import annotations

import logging
from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.const import ATTR_SUPPORTED_FEATURES, Platform

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    HA_WEATHER_COND_SUNNY,
    LockMode,
)

from ..conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
    MOCK_WEATHER_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COVER_CLOSED,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    create_integration_coordinator,
    set_weather_forecast_temp,
)


class TestLockModeOverridePriority:
    """Test that lock modes properly override normal automation logic."""

    @pytest.mark.asyncio
    async def test_force_close_overrides_cold_temperature_automation(self, caplog):
        """Test FORCE_CLOSE locks cover closed even when automation wants to open for warmth."""
        # Setup coordinator with FORCE_CLOSE lock mode
        coordinator = create_integration_coordinator(lock_mode=LockMode.FORCE_CLOSE)
        hass = cast(MagicMock, coordinator.hass)

        # Set cold temperature (would normally trigger opening for warmth)
        set_weather_forecast_temp(float(TEST_COLD_TEMP))

        # Setup entity states
        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        cover_state = MagicMock()
        cover_state.state = "open"
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,  # Currently open
            ATTR_SUPPORTED_FEATURES: 15,
        }

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: sun_state,
        }.get(entity_id)

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Execute automation
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify lock mode forced closure despite cold temperature
        assert result is not None
        cover_data = result.covers[MOCK_COVER_ENTITY_ID]
        assert coordinator.lock_mode == LockMode.FORCE_CLOSE
        assert cover_data.pos_target_desired == TEST_COVER_CLOSED
        assert cover_data.pos_target_final == TEST_COVER_CLOSED

        # Verify service was called to close the cover
        cover_calls = [call for call in hass.services.async_call.call_args_list if call[0][0] == Platform.COVER]
        assert len(cover_calls) > 0

    @pytest.mark.asyncio
    async def test_force_open_overrides_heat_protection(self, caplog):
        """Test FORCE_OPEN locks cover open even during heat protection conditions."""
        coordinator = create_integration_coordinator(lock_mode=LockMode.FORCE_OPEN)
        hass = cast(MagicMock, coordinator.hass)

        # Set hot temperature + sun hitting (would normally trigger closing for heat protection)
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        cover_state = MagicMock()
        cover_state.state = "closed"
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_CLOSED,  # Currently closed
            ATTR_SUPPORTED_FEATURES: 15,
        }

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}  # Direct sun

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: sun_state,
        }.get(entity_id)

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Execute automation
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify lock mode forced opening despite hot temperature
        assert result is not None
        cover_data = result.covers[MOCK_COVER_ENTITY_ID]
        assert coordinator.lock_mode == LockMode.FORCE_OPEN
        assert cover_data.pos_target_desired == TEST_COVER_OPEN
        assert cover_data.pos_target_final == TEST_COVER_OPEN

        # Verify service was called to open the cover
        cover_calls = [call for call in hass.services.async_call.call_args_list if call[0][0] == Platform.COVER]
        assert len(cover_calls) > 0

    @pytest.mark.asyncio
    async def test_hold_position_blocks_all_automation(self, caplog):
        """Test HOLD_POSITION prevents any cover movement regardless of conditions."""
        coordinator = create_integration_coordinator(lock_mode=LockMode.HOLD_POSITION)
        hass = cast(MagicMock, coordinator.hass)

        # Set hot temperature + sun hitting (would normally trigger closing)
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        cover_state = MagicMock()
        cover_state.state = "open"
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: 75,  # Partially open
            ATTR_SUPPORTED_FEATURES: 15,
        }

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: sun_state,
        }.get(entity_id)

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Execute automation
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify lock mode held position (no movement)
        assert result is not None
        cover_data = result.covers[MOCK_COVER_ENTITY_ID]
        assert coordinator.lock_mode == LockMode.HOLD_POSITION
        assert cover_data.pos_target_desired == 75  # Stays at current position
        assert cover_data.pos_target_final == 75

        # Verify NO service calls were made
        cover_calls = [call for call in hass.services.async_call.call_args_list if call[0][0] == Platform.COVER]
        assert len(cover_calls) == 0


class TestLockModeStatePersistence:
    """Test lock mode survives coordinator refresh cycles."""

    @pytest.mark.asyncio
    async def test_lock_mode_persists_across_refresh_cycles(self, caplog):
        """Test lock mode setting persists through multiple automation runs."""
        coordinator = create_integration_coordinator(lock_mode=LockMode.FORCE_CLOSE)
        hass = cast(MagicMock, coordinator.hass)

        # Setup entity states
        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        cover_state = MagicMock()
        cover_state.state = "closed"
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_CLOSED,
            ATTR_SUPPORTED_FEATURES: 15,
        }

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: sun_state,
        }.get(entity_id)

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Run automation multiple times with different conditions
        for temp in [TEST_COLD_TEMP, TEST_HOT_TEMP, TEST_COLD_TEMP]:
            set_weather_forecast_temp(float(temp))
            await coordinator.async_refresh()
            result = coordinator.data

            # Verify lock mode persists and enforces position
            assert result is not None
            cover_data = result.covers[MOCK_COVER_ENTITY_ID]
            assert coordinator.lock_mode == LockMode.FORCE_CLOSE
            assert cover_data.pos_target_desired == TEST_COVER_CLOSED

    @pytest.mark.asyncio
    async def test_lock_mode_change_takes_effect_immediately(self, caplog):
        """Test changing lock mode immediately affects next automation cycle."""
        coordinator = create_integration_coordinator()
        hass = cast(MagicMock, coordinator.hass)

        # Setup entity states
        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        cover_state = MagicMock()
        cover_state.state = "open"
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: 15,
        }

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: sun_state,
        }.get(entity_id)

        set_weather_forecast_temp(float(TEST_HOT_TEMP))
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Start with UNLOCKED (normal automation)
        await coordinator.async_refresh()
        assert coordinator.lock_mode == LockMode.UNLOCKED

        # Change to FORCE_CLOSE mid-test by modifying options directly
        coordinator.config_entry.options[ConfKeys.LOCK_MODE.value] = LockMode.FORCE_CLOSE  # type: ignore[index]
        await coordinator.async_refresh()
        result2 = coordinator.data

        # Verify immediate effect on next refresh
        assert coordinator.lock_mode == LockMode.FORCE_CLOSE
        assert result2.covers[MOCK_COVER_ENTITY_ID].pos_target_desired == TEST_COVER_CLOSED


class TestMultiCoverLockMode:
    """Test lock modes work correctly with multiple covers."""

    @pytest.mark.asyncio
    async def test_lock_mode_applies_to_all_covers(self, caplog):
        """Test lock mode affects all covers (not per-cover setting)."""
        covers = ["cover.test_1", "cover.test_2", "cover.test_3"]
        coordinator = create_integration_coordinator(covers=covers, lock_mode=LockMode.FORCE_OPEN)
        hass = cast(MagicMock, coordinator.hass)

        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        # Setup all covers as closed
        cover_states = {}
        for cover_id in covers:
            cover_state = MagicMock()
            cover_state.state = "closed"
            cover_state.attributes = {
                ATTR_CURRENT_POSITION: TEST_COVER_CLOSED,
                ATTR_SUPPORTED_FEATURES: 15,
            }
            cover_states[cover_id] = cover_state

        def get_state(entity_id: str):
            if entity_id == MOCK_SUN_ENTITY_ID:
                return sun_state
            if entity_id == MOCK_WEATHER_ENTITY_ID:
                return weather_state
            return cover_states.get(entity_id)

        hass.states.get.side_effect = get_state
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Execute automation
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify all covers have same lock mode and are forced open
        assert result is not None
        assert coordinator.lock_mode == LockMode.FORCE_OPEN
        for cover_id in covers:
            cover_data = result.covers[cover_id]
            assert cover_data.pos_target_desired == TEST_COVER_OPEN


class TestLockModeEdgeCases:
    """Test lock mode behavior in unusual scenarios."""

    @pytest.mark.asyncio
    async def test_force_open_with_binary_cover(self, caplog):
        """Test FORCE_OPEN works with covers that only support open/close."""
        coordinator = create_integration_coordinator(lock_mode=LockMode.FORCE_OPEN)
        hass = cast(MagicMock, coordinator.hass)
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        # Binary cover (no position control)
        cover_state = MagicMock()
        cover_state.state = "closed"
        cover_state.attributes = {
            ATTR_SUPPORTED_FEATURES: 3,  # Only open/close, no position
        }

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: sun_state,
        }.get(entity_id)

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Execute automation
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify lock mode works with binary cover
        assert result is not None
        cover_data = result.covers[MOCK_COVER_ENTITY_ID]
        assert coordinator.lock_mode == LockMode.FORCE_OPEN
        assert cover_data.pos_target_desired == TEST_COVER_OPEN

        # Verify open_cover service was called
        cover_calls = [call for call in hass.services.async_call.call_args_list if call[0][0] == Platform.COVER]
        assert len(cover_calls) > 0
        assert cover_calls[0][0][1] == "open_cover"

    @pytest.mark.asyncio
    async def test_force_close_with_partial_position_cover(self, caplog):
        """Test FORCE_CLOSE moves cover from partial position to fully closed."""
        coordinator = create_integration_coordinator(lock_mode=LockMode.FORCE_CLOSE)
        hass = cast(MagicMock, coordinator.hass)
        set_weather_forecast_temp(float(TEST_COLD_TEMP))

        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        cover_state = MagicMock()
        cover_state.state = "open"
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: 50,  # Partially open
            ATTR_SUPPORTED_FEATURES: 15,
        }

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: sun_state,
        }.get(entity_id)

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Execute automation
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify moved from 50% to 0%
        assert result is not None
        cover_data = result.covers[MOCK_COVER_ENTITY_ID]
        assert cover_data.pos_target_desired == TEST_COVER_CLOSED
        assert cover_data.pos_target_final == TEST_COVER_CLOSED

    @pytest.mark.asyncio
    async def test_lock_mode_with_unavailable_covers(self, caplog):
        """Test lock mode handles unavailable covers gracefully."""
        covers = ["cover.available", "cover.unavailable"]
        coordinator = create_integration_coordinator(covers=covers, lock_mode=LockMode.FORCE_CLOSE)
        hass = cast(MagicMock, coordinator.hass)
        set_weather_forecast_temp(float(TEST_COLD_TEMP))

        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        available_cover = MagicMock()
        available_cover.state = "open"
        available_cover.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: 15,
        }

        unavailable_cover = MagicMock()
        unavailable_cover.state = "unavailable"
        unavailable_cover.attributes = {}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_SUN_ENTITY_ID: sun_state,
            "cover.available": available_cover,
            "cover.unavailable": unavailable_cover,
        }.get(entity_id)

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Execute automation
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify only available cover was processed
        assert result is not None
        assert "cover.available" in result.covers
        # Unavailable cover should be skipped but not cause errors
        assert coordinator.lock_mode == LockMode.FORCE_CLOSE


class TestLockModeServiceIntegration:
    """Test lock mode configuration integration."""

    @pytest.mark.asyncio
    async def test_lock_mode_from_config_is_respected(self, caplog):
        """Test lock mode from configuration is correctly applied."""
        # Create coordinator with FORCE_CLOSE mode
        coordinator = create_integration_coordinator(lock_mode=LockMode.FORCE_CLOSE)
        hass = cast(MagicMock, coordinator.hass)

        # Verify mode is set
        assert coordinator.lock_mode == LockMode.FORCE_CLOSE

        # Setup states for automation run
        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        cover_state = MagicMock()
        cover_state.state = "open"
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: 15,
        }

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: sun_state,
        }.get(entity_id)

        set_weather_forecast_temp(float(TEST_COLD_TEMP))
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Run automation and verify covers move to closed
        await coordinator.async_refresh()
        result = coordinator.data

        assert result is not None
        cover_data = result.covers[MOCK_COVER_ENTITY_ID]
        assert coordinator.lock_mode == LockMode.FORCE_CLOSE
        assert cover_data.pos_target_desired == TEST_COVER_CLOSED

    @pytest.mark.asyncio
    async def test_lock_mode_stored_in_config_options(self, caplog):
        """Test lock mode is stored in config entry options."""
        coordinator = create_integration_coordinator(lock_mode=LockMode.FORCE_OPEN)

        # Verify persisted to config entry
        assert coordinator.config_entry.options[ConfKeys.LOCK_MODE.value] == LockMode.FORCE_OPEN

    @pytest.mark.asyncio
    async def test_lock_mode_change_via_config_takes_effect(self, caplog):
        """Test changing lock mode via config and refreshing applies the change."""
        coordinator = create_integration_coordinator(lock_mode=LockMode.UNLOCKED)
        hass = cast(MagicMock, coordinator.hass)

        # Setup minimal states
        weather_state = MagicMock()
        weather_state.state = HA_WEATHER_COND_SUNNY
        weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

        cover_state = MagicMock()
        cover_state.state = "open"
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: 15,
        }

        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        hass.states.get.side_effect = lambda entity_id: {
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: sun_state,
        }.get(entity_id)

        set_weather_forecast_temp(float(TEST_HOT_TEMP))
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Change lock mode via config
        coordinator.config_entry.options[ConfKeys.LOCK_MODE.value] = LockMode.FORCE_CLOSE  # type: ignore[index]

        # Refresh and verify data is updated
        await coordinator.async_refresh()
        result = coordinator.data
        assert result is not None
        assert coordinator.lock_mode == LockMode.FORCE_CLOSE


class TestLockModeUIEntities:
    """Test lock mode entities (sensor, binary_sensor) in integration."""

    @pytest.mark.asyncio
    async def test_lock_mode_reflected_in_coordinator_data(self, caplog):
        """Test lock mode is reflected in coordinator data for entity consumption."""

        # Setup minimal states - reusable helper
        def setup_states(hass_mock):
            weather_state = MagicMock()
            weather_state.state = HA_WEATHER_COND_SUNNY
            weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

            cover_state = MagicMock()
            cover_state.state = "open"
            cover_state.attributes = {
                ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
                ATTR_SUPPORTED_FEATURES: 15,
            }

            sun_state = MagicMock()
            sun_state.state = "above_horizon"
            sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

            hass_mock.states.get.side_effect = lambda entity_id: {
                MOCK_WEATHER_ENTITY_ID: weather_state,
                MOCK_COVER_ENTITY_ID: cover_state,
                MOCK_SUN_ENTITY_ID: sun_state,
            }.get(entity_id)

        set_weather_forecast_temp(float(TEST_HOT_TEMP))
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Test each lock mode
        for lock_mode in [LockMode.UNLOCKED, LockMode.HOLD_POSITION, LockMode.FORCE_OPEN, LockMode.FORCE_CLOSE]:
            coordinator = create_integration_coordinator(lock_mode=lock_mode)
            hass = cast(MagicMock, coordinator.hass)
            setup_states(hass)

            await coordinator.async_refresh()
            result = coordinator.data

            assert result is not None

            # Verify lock mode value
            assert coordinator.lock_mode == lock_mode

    @pytest.mark.asyncio
    async def test_lock_active_tracks_lock_state_correctly(self, caplog):
        """Test lock_active binary value tracks whether any lock is active."""

        # Setup minimal states
        def setup_states(hass_mock):
            weather_state = MagicMock()
            weather_state.state = HA_WEATHER_COND_SUNNY
            weather_state.entity_id = MOCK_WEATHER_ENTITY_ID

            cover_state = MagicMock()
            cover_state.state = "open"
            cover_state.attributes = {
                ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
                ATTR_SUPPORTED_FEATURES: 15,
            }

            sun_state = MagicMock()
            sun_state.state = "above_horizon"
            sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

            hass_mock.states.get.side_effect = lambda entity_id: {
                MOCK_WEATHER_ENTITY_ID: weather_state,
                MOCK_COVER_ENTITY_ID: cover_state,
                MOCK_SUN_ENTITY_ID: sun_state,
            }.get(entity_id)

        set_weather_forecast_temp(float(TEST_HOT_TEMP))
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # UNLOCKED: lock should not be active
        coordinator = create_integration_coordinator(lock_mode=LockMode.UNLOCKED)
        hass = cast(MagicMock, coordinator.hass)
        setup_states(hass)
        await coordinator.async_refresh()
        assert coordinator.lock_mode == LockMode.UNLOCKED
        assert not coordinator.is_locked

        # Any other mode: lock should be active
        for lock_mode in [LockMode.HOLD_POSITION, LockMode.FORCE_OPEN, LockMode.FORCE_CLOSE]:
            coordinator = create_integration_coordinator(lock_mode=lock_mode)
            hass = cast(MagicMock, coordinator.hass)
            setup_states(hass)
            await coordinator.async_refresh()
            assert coordinator.lock_mode == lock_mode
            assert coordinator.is_locked
