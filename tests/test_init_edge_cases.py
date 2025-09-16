"""Tests for edge cases in integration setup and teardown.

This module contains focused tests for edge cases and error conditions in the
integration's initialization and cleanup processes that are not covered by
the main integration tests.

Coverage targets:
- Exception handling during setup and teardown
- Error recovery scenarios during integration lifecycle
- Edge cases in configuration validation during setup
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.smart_cover_automation import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_setup_entry_unexpected_exception() -> None:
    """Test handling of unexpected exceptions during integration setup.

    This test verifies that the integration gracefully handles unexpected
    errors during setup and returns False to indicate setup failure to
    Home Assistant.

    Coverage target: __init__.py lines 87-90 (unexpected exception handling)
    """
    # Create mock Home Assistant instance with required attributes
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}  # Required for async_get_loaded_integration
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    # Create configuration entry
    config_entry = MockConfigEntry(create_temperature_config())

    # Mock async_get_loaded_integration to raise unexpected exception
    with patch("custom_components.smart_cover_automation.async_get_loaded_integration") as mock_get_integration:
        mock_get_integration.side_effect = RuntimeError("Unexpected setup error")

        # Execute setup and verify graceful failure handling
        result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        # Setup should return False indicating failure
        assert result is False

        # Verify the exception was attempted (async_get_loaded_integration was called)
        mock_get_integration.assert_called_once_with(hass, config_entry.domain)


@pytest.mark.asyncio
async def test_unload_entry_unexpected_exception() -> None:
    """Test handling of unexpected exceptions during integration unload.

    This test verifies that the integration gracefully handles unexpected
    errors during unload and returns False to indicate unload failure to
    Home Assistant.

    Coverage target: __init__.py lines 117-120 (unexpected exception handling)
    """
    # Create mock Home Assistant instance
    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()

    # Configure async_unload_platforms to raise unexpected exception
    hass.config_entries.async_unload_platforms = AsyncMock(side_effect=RuntimeError("Unexpected unload error"))

    # Create configuration entry with mock runtime data
    config_entry = MockConfigEntry(create_temperature_config())
    coordinator = MagicMock()
    config_entry.runtime_data.coordinator = coordinator

    # Execute unload and verify graceful failure handling
    result = await async_unload_entry(hass, cast(IntegrationConfigEntry, config_entry))

    # Unload should return False indicating failure
    assert result is False

    # Verify the exception was attempted to be handled
    hass.config_entries.async_unload_platforms.assert_called_once()


@pytest.mark.asyncio
async def test_setup_entry_config_entry_not_ready_exception() -> None:
    """Test handling of ConfigEntryNotReady exception during coordinator setup.

    This test verifies that the integration properly handles ConfigEntryNotReady
    exceptions that can occur when dependencies are not available during startup.
    Based on the code, ConfigEntryNotReady exceptions are caught and logged,
    returning False instead of re-raising.

    Coverage target: Ensure proper exception handling flow in setup
    """
    # Create mock Home Assistant instance with required attributes
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {}  # Required for async_get_loaded_integration
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    # Create configuration entry
    config_entry = MockConfigEntry(create_temperature_config())

    # Mock DataUpdateCoordinator to raise ConfigEntryNotReady
    with patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator_class.side_effect = ConfigEntryNotReady("Dependencies not ready")

        # Execute setup and verify it returns False (doesn't re-raise)
        result = await async_setup_entry(hass, cast(IntegrationConfigEntry, config_entry))

        # Setup should return False indicating failure (exception is caught)
        assert result is False

        # Verify the coordinator was attempted to be created
        mock_coordinator_class.assert_called_once_with(hass, config_entry)
