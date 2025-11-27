"""Unit tests for lock mode validation in DataUpdateCoordinator.

This module tests the async_set_lock_mode method, focusing on:
- Valid lock mode acceptance
- Invalid lock mode rejection with proper error messages
- Config entry update behavior
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.const import LockMode
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator

from ..conftest import MockConfigEntry, create_temperature_config


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
        return DataUpdateCoordinator(mock_hass, config_entry)

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
        coordinator.config_entry.options = {
            "lock_mode": LockMode.UNLOCKED,
            "covers": ["cover.test"],
            "temp_threshold": 25,
        }

        new_mode = LockMode.HOLD_POSITION
        await coordinator.async_set_lock_mode(new_mode)

        # Verify other options are preserved
        call_args = coordinator.hass.config_entries.async_update_entry.call_args
        new_options = call_args[1]["options"]

        assert new_options["lock_mode"] == new_mode
        assert new_options["covers"] == ["cover.test"]
        assert new_options["temp_threshold"] == 25
