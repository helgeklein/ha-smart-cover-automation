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
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.smart_cover_automation import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry


@pytest.mark.parametrize(
    "exception_type,mock_target,exception_message,test_description",
    [
        (
            RuntimeError,
            "custom_components.smart_cover_automation.async_get_loaded_integration",
            "Unexpected setup error",
            "setup exception from async_get_loaded_integration",
        ),
        (
            ValueError,
            "custom_components.smart_cover_automation.DataUpdateCoordinator",
            "Invalid configuration",
            "setup exception from DataUpdateCoordinator",
        ),
        (
            ConnectionError,
            "custom_components.smart_cover_automation.DataUpdateCoordinator",
            "Connection failed",
            "setup exception from connection failure",
        ),
    ],
)
async def test_setup_entry_various_exceptions(
    mock_hass_with_spec, mock_config_entry_basic, exception_type: type, mock_target: str, exception_message: str, test_description: str
) -> None:
    """Test handling of various exception types during integration setup.

    This parametrized test verifies that the integration gracefully handles different
    types of exceptions that can occur during setup and always returns False to
    indicate setup failure to Home Assistant.
    """
    # Ensure hass has the required data structure
    mock_hass_with_spec.data = {}  # Required for async_get_loaded_integration

    # Mock the target to raise the specified exception
    with patch(mock_target) as mock_component:
        mock_component.side_effect = exception_type(exception_message)

        # Execute setup and verify graceful failure handling
        result = await async_setup_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

        # Setup should return False indicating failure
        assert result is False, f"Setup should return False for {test_description}"

        # Verify the exception was attempted
        mock_component.assert_called_once()


@pytest.mark.parametrize(
    "exception_type,exception_message,test_description",
    [
        (RuntimeError, "Unexpected unload error", "runtime error during unload"),
        (ValueError, "Invalid platform configuration", "value error during platform unload"),
        (ConnectionError, "Service connection lost", "connection error during unload"),
    ],
)
async def test_unload_entry_various_exceptions(
    mock_hass_with_spec, mock_config_entry_basic, exception_type: type, exception_message: str, test_description: str
) -> None:
    """Test handling of various exception types during integration unload.

    This parametrized test verifies that the integration gracefully handles different
    types of exceptions that can occur during unload and always returns False to
    indicate unload failure to Home Assistant.
    """
    # Configure async_unload_platforms to raise the specified exception
    mock_hass_with_spec.config_entries.async_unload_platforms = AsyncMock(side_effect=exception_type(exception_message))

    # Create configuration entry with mock runtime data
    coordinator = MagicMock()
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Execute unload and verify graceful failure handling
    result = await async_unload_entry(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Unload should return False indicating failure
    assert result is False, f"Unload should return False for {test_description}"

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
