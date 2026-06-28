"""Unit tests for lock mode validation in DataUpdateCoordinator.

This module tests the async_set_lock_mode method, focusing on:
- Valid lock mode acceptance
- Invalid lock mode rejection with proper error messages
- Config entry update behavior
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.smart_cover_automation.const import HeatProtectionMode, LockMode, ReopeningMode
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator

from ..conftest import MockConfigEntry, create_temperature_config, set_test_options


class TestLockModeValidation:
    """Test lock mode validation in async_set_lock_mode method."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.config_entries = MagicMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=None)
        return hass

    @pytest.fixture
    def coordinator(self, mock_hass):
        """Create a coordinator instance for testing."""
        config_entry = MockConfigEntry(create_temperature_config())
        return DataUpdateCoordinator(mock_hass, config_entry)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "lock_mode",
        [
            LockMode.UNLOCKED,
            LockMode.HOLD_POSITION,
            LockMode.FORCE_OPEN,
            LockMode.FORCE_CLOSE,
        ],
    )
    async def test_async_set_lock_mode_valid_modes(self, coordinator, lock_mode):
        """Test that all valid LockMode enum values are accepted."""
        # Should not raise any exception
        await coordinator.async_set_lock_mode(lock_mode)

        # Verify config entry was updated
        coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_args = coordinator.hass.config_entries.async_update_entry.call_args
        assert call_args[1]["options"]["lock_mode"] == lock_mode

    async def test_async_set_lock_mode_invalid_mode_raises_value_error(self, coordinator, caplog):
        """Test that invalid lock mode raises ValueError with proper message."""
        invalid_mode = "invalid_lock_mode"

        with pytest.raises(ValueError, match=f"Invalid lock mode: {invalid_mode}"):
            await coordinator.async_set_lock_mode(invalid_mode)

        # Verify error was logged
        assert f"Invalid lock mode: {invalid_mode}" in caplog.text
        assert "Valid modes:" in caplog.text

        # Verify config entry was NOT updated
        coordinator.hass.config_entries.async_update_entry.assert_not_called()

    async def test_async_set_lock_mode_invalid_mode_logs_valid_modes(self, coordinator, caplog):
        """Test that error log includes list of valid modes."""
        with pytest.raises(ValueError):
            await coordinator.async_set_lock_mode("bad_mode")

        # Verify all valid modes are mentioned in the log
        assert "unlocked" in caplog.text
        assert "hold_position" in caplog.text
        assert "force_open" in caplog.text
        assert "force_close" in caplog.text

    @pytest.mark.parametrize(
        "invalid_mode",
        [
            "UNLOCKED",  # Wrong case
            "lock",
            "unlock",
            "hold",
            "force_up",
            "force_down",
            "",
            "None",
            123,  # Wrong type
        ],
    )
    async def test_async_set_lock_mode_various_invalid_modes(self, coordinator, invalid_mode):
        """Test that various invalid lock mode values are rejected."""
        with pytest.raises(ValueError, match="Invalid lock mode"):
            await coordinator.async_set_lock_mode(invalid_mode)

        # Config should not be updated
        coordinator.hass.config_entries.async_update_entry.assert_not_called()

    async def test_async_set_lock_mode_updates_config_entry_options(self, coordinator):
        """Test that valid lock mode updates the config entry options."""
        new_mode = LockMode.FORCE_CLOSE

        await coordinator.async_set_lock_mode(new_mode)

        # Verify async_update_entry was called with correct arguments
        coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_args = coordinator.hass.config_entries.async_update_entry.call_args

        # First positional arg should be the config entry
        assert call_args[0][0] == coordinator.config_entry

        # Options should contain the new lock mode
        assert "options" in call_args[1]
        assert call_args[1]["options"]["lock_mode"] == new_mode

    async def test_async_set_lock_mode_preserves_other_options(self, coordinator):
        """Test that setting lock mode preserves other config options."""
        # Add some existing options
        set_test_options(
            coordinator.config_entry,
            {
                "lock_mode": LockMode.UNLOCKED,
                "covers": ["cover.test"],
                "daily_max_temperature_threshold": 25,
            },
        )

        new_mode = LockMode.HOLD_POSITION
        await coordinator.async_set_lock_mode(new_mode)

        # Verify other options are preserved
        call_args = coordinator.hass.config_entries.async_update_entry.call_args
        new_options = call_args[1]["options"]

        assert new_options["lock_mode"] == new_mode
        assert new_options["covers"] == ["cover.test"]
        assert new_options["daily_max_temperature_threshold"] == 25


class TestAutomaticReopeningModeValidation:
    """Test automatic reopening mode validation in DataUpdateCoordinator."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.config_entries = MagicMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=None)
        return hass

    @pytest.fixture
    def coordinator(self, mock_hass):
        """Create a coordinator instance for testing."""
        config_entry = MockConfigEntry(create_temperature_config())
        return DataUpdateCoordinator(mock_hass, config_entry)  # type: ignore[arg-type]

    @pytest.mark.parametrize("mode", [ReopeningMode.ACTIVE, ReopeningMode.PASSIVE, ReopeningMode.OFF])
    async def test_async_set_automatic_reopening_mode_valid_modes(self, coordinator, mode):
        """Test that all valid automatic reopening modes are accepted."""

        await coordinator.async_set_automatic_reopening_mode(mode)

        coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_args = coordinator.hass.config_entries.async_update_entry.call_args
        assert call_args[1]["options"]["automatic_reopening_mode"] == mode

    async def test_async_set_automatic_reopening_mode_invalid_mode_raises_value_error(self, coordinator, caplog):
        """Test that invalid automatic reopening mode raises ValueError."""

        invalid_mode = "invalid_reopening_mode"

        with pytest.raises(ValueError, match=f"Invalid automatic reopening mode: {invalid_mode}"):
            await coordinator.async_set_automatic_reopening_mode(invalid_mode)

        assert f"Invalid automatic reopening mode: {invalid_mode}" in caplog.text
        coordinator.hass.config_entries.async_update_entry.assert_not_called()


class TestHeatProtectionModeValidation:
    """Test heat protection mode validation in DataUpdateCoordinator."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.config_entries = MagicMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=None)
        return hass

    @pytest.fixture
    def coordinator(self, mock_hass):
        """Create a coordinator instance for testing."""
        config_entry = MockConfigEntry(create_temperature_config())
        return DataUpdateCoordinator(mock_hass, config_entry)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "mode",
        [
            HeatProtectionMode.OFF,
            HeatProtectionMode.AUTO,
            HeatProtectionMode.FORCED_SUNNY_WINDOWS,
            HeatProtectionMode.FORCED_ALL_WINDOWS,
        ],
    )
    async def test_async_set_heat_protection_mode_valid_modes(self, coordinator, mode):
        """Test that all valid heat protection modes are accepted."""

        await coordinator.async_set_heat_protection_mode(mode)

        coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_args = coordinator.hass.config_entries.async_update_entry.call_args
        assert call_args[1]["options"]["heat_protection_mode"] == mode

    async def test_async_set_heat_protection_mode_invalid_mode_raises_value_error(self, coordinator, caplog):
        """Test that invalid heat protection mode raises ValueError."""

        invalid_mode = "invalid_heat_protection_mode"

        with pytest.raises(ValueError, match=f"Invalid heat protection mode: {invalid_mode}"):
            await coordinator.async_set_heat_protection_mode(invalid_mode)

        assert f"Invalid heat protection mode: {invalid_mode}" in caplog.text
        coordinator.hass.config_entries.async_update_entry.assert_not_called()


class TestCoordinatorRuntimeStateAndProperties:
    """Test coordinator helper methods that proxy runtime state and properties."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = MagicMock()
        hass.config_entries = MagicMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.states = MagicMock()
        hass.states.get = MagicMock(return_value=None)
        return hass

    @pytest.fixture
    def coordinator(self, mock_hass):
        """Create a coordinator instance for testing."""
        config_entry = MockConfigEntry(create_temperature_config())
        return DataUpdateCoordinator(mock_hass, config_entry)  # type: ignore[arg-type]

    async def test_async_restore_runtime_state_restores_both_persisted_payloads(self, coordinator):
        """Test restoring persisted markers and temperature extrema into the engine."""

        stored_markers = {"cover.test": "heat_protection"}
        stored_extrema = {"date": "2026-05-24", "temp_max": 25.0, "temp_min": 15.0}
        coordinator._automation_state_store = MagicMock(
            async_load_closed_markers=AsyncMock(return_value=stored_markers),
            async_load_current_day_temperature_extrema=AsyncMock(return_value=stored_extrema),
        )
        coordinator._automation_engine = MagicMock(
            restore_closed_by_automation_markers=MagicMock(),
            restore_current_day_temperature_extrema=MagicMock(),
        )

        await coordinator.async_restore_runtime_state()

        coordinator._automation_state_store.async_load_closed_markers.assert_awaited_once()
        coordinator._automation_state_store.async_load_current_day_temperature_extrema.assert_awaited_once()
        coordinator._automation_engine.restore_closed_by_automation_markers.assert_called_once_with(stored_markers)
        coordinator._automation_engine.restore_current_day_temperature_extrema.assert_called_once_with(stored_extrema)

    async def test_async_persist_runtime_state_saves_both_engine_exports(self, coordinator):
        """Test persisting both runtime-state payloads from the automation engine."""

        exported_markers = {"cover.test": "manual_override"}
        exported_extrema = {"date": "2026-05-24", "temp_max": 28.0, "temp_min": 17.0}
        coordinator._automation_engine = MagicMock(
            export_closed_by_automation_markers=MagicMock(return_value=exported_markers),
            export_current_day_temperature_extrema=MagicMock(return_value=exported_extrema),
        )
        coordinator._automation_state_store = MagicMock(
            async_save_closed_markers=AsyncMock(),
            async_save_current_day_temperature_extrema=AsyncMock(),
        )

        await coordinator.async_persist_runtime_state()

        coordinator._automation_state_store.async_save_closed_markers.assert_awaited_once_with(exported_markers)
        coordinator._automation_state_store.async_save_current_day_temperature_extrema.assert_awaited_once_with(exported_extrema)

    async def test_async_remove_runtime_state_delegates_to_state_store(self, coordinator):
        """Test removing persisted runtime state."""

        coordinator._automation_state_store = MagicMock(async_remove=AsyncMock())

        await coordinator.async_remove_runtime_state()

        coordinator._automation_state_store.async_remove.assert_awaited_once()

    def test_cancel_pending_cover_executions_delegates_to_engine(self, coordinator):
        """Test canceling queued cover executions through the automation engine."""

        coordinator._automation_engine = MagicMock(cancel_pending_cover_executions=MagicMock())

        coordinator.cancel_pending_cover_executions()

        coordinator._automation_engine.cancel_pending_cover_executions.assert_called_once()

    def test_status_sensor_unique_id_proxies_to_ha_interface(self, coordinator):
        """Test status sensor unique ID getter and setter proxy through the HA interface."""

        coordinator.status_sensor_unique_id = "binary_sensor.smart_cover_automation_status"

        assert coordinator.status_sensor_unique_id == "binary_sensor.smart_cover_automation_status"

    def test_is_locked_and_heat_protection_mode_follow_current_options(self, coordinator):
        """Test resolved properties follow the current config entry options."""

        assert coordinator.is_locked is False
        assert coordinator.heat_protection_mode == HeatProtectionMode.AUTO

        updated_options = {
            **dict(coordinator.config_entry.options),
            "lock_mode": LockMode.FORCE_CLOSE,
            "heat_protection_mode": HeatProtectionMode.FORCED_ALL_WINDOWS,
        }
        set_test_options(coordinator.config_entry, updated_options)

        assert coordinator.is_locked is True
        assert coordinator.heat_protection_mode == HeatProtectionMode.FORCED_ALL_WINDOWS
