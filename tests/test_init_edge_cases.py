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

from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.smart_cover_automation import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry


async def test_setup_entry_unexpected_exception(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test handling of unexpected exceptions during integration setup.

    This test verifies that the integration gracefully handles unexpected
    errors during setup and returns False to indicate setup failure to
    Home Assistant.

    Coverage target: __init__.py lines 87-90 (unexpected exception handling)
    """
    # Ensure hass has the required data structure
    mock_hass_with_spec.data = {}  # Required for async_get_loaded_integration

    # Mock async_get_loaded_integration to raise unexpected exception
    with patch("custom_components.smart_cover_automation.async_get_loaded_integration") as mock_get_integration:
        mock_get_integration.side_effect = RuntimeError("Unexpected setup error")

        # Execute setup and verify graceful failure handling
        result = await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Setup should return False indicating failure
        assert result is False

        # Verify the exception was attempted (async_get_loaded_integration was called)
        mock_get_integration.assert_called_once_with(mock_hass_with_spec, mock_config_entry_basic.domain)


async def test_unload_entry_unexpected_exception(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test handling of unexpected exceptions during integration unload.

    This test verifies that the integration gracefully handles unexpected
    errors during unload and returns False to indicate unload failure to
    Home Assistant.

    Coverage target: __init__.py lines 117-120 (unexpected exception handling)
    """
    # Configure async_unload_platforms to raise unexpected exception
    mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(side_effect=RuntimeError("Unexpected unload error"))

    # Create configuration entry with mock runtime data
    coordinator = MagicMock()
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Execute unload and verify graceful failure handling
    result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Unload should return False indicating failure
    assert result is False

    # Verify the exception was attempted to be handled
    mock_hass_with_spec.config_entries.async_unload_platforms.assert_called_once()


async def test_setup_entry_config_entry_not_ready(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test setup handling when ConfigEntryNotReady is raised.

    This test verifies that the integration properly handles ConfigEntryNotReady
    exceptions that can occur when dependencies are not available during startup.
    Based on the code, ConfigEntryNotReady exceptions are caught and logged,
    returning False instead of re-raising.

    Coverage target: Ensure proper exception handling flow in setup
    """
    # Ensure hass has the required data structure
    mock_hass_with_spec.data = {}  # Required for async_get_loaded_integration

    # Mock DataUpdateCoordinator to raise ConfigEntryNotReady
    with patch("custom_components.smart_cover_automation.DataUpdateCoordinator") as mock_coordinator_class:
        mock_coordinator_class.side_effect = ConfigEntryNotReady("Dependencies not ready")
