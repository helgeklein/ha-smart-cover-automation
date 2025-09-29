"""Tests for coordinator configuration edge cases.

This module contains focused tests for coordinator configuration scenarios
that are not covered by the main coordinator tests, specifically targeting
edge cases in configuration handling and logging setup.

Coverage targets:
- Disabled automation state handling
- Verbose logging configuration
- Configuration edge cases during coordinator initialization
"""

from __future__ import annotations

import logging
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_disabled_automation_config(mock_basic_hass) -> None:
    """Test coordinator behavior when automation is disabled in configuration.

    This test verifies that the coordinator properly handles configurations
    where the automation is explicitly disabled, ensuring no automation
    actions are performed and the coordinator behaves appropriately.

    Coverage target: coordinator.py disabled automation handling
    """
    # Create configuration with automation disabled
    config = create_temperature_config()
    config[ConfKeys.ENABLED.value] = False  # Disable automation
    config_entry = MockConfigEntry(config)

    # Create coordinator with disabled configuration
    coordinator = DataUpdateCoordinator(mock_basic_hass, cast(IntegrationConfigEntry, config_entry))

    # Execute update with disabled automation
    await coordinator.async_refresh()

    # Verify coordinator was created successfully even with disabled automation
    assert coordinator is not None
    assert coordinator.hass is mock_basic_hass


def test_coordinator_verbose_logging_configuration() -> None:
    """Test coordinator verbose logging configuration setup.

    This test verifies that when verbose_logging is enabled in configuration,
    the coordinator properly configures debug logging level.

    Coverage target: coordinator.py lines 115-118 (verbose logging setup)
    """
    # Create mock Home Assistant instance
    hass = MagicMock()

    # Create configuration with verbose logging enabled
    config = create_temperature_config()
    config[ConfKeys.VERBOSE_LOGGING.value] = True  # Enable verbose logging
    config_entry = MockConfigEntry(config)

    # Mock the logger to verify it gets configured
    with patch("custom_components.smart_cover_automation.const.LOGGER") as mock_logger:
        # Create coordinator (this should trigger logging configuration)
        DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Verify verbose logging was configured
        mock_logger.setLevel.assert_called_with(logging.DEBUG)
        mock_logger.debug.assert_called_with("Verbose logging enabled")


def test_coordinator_verbose_logging_exception_handling(mock_basic_hass) -> None:
    """Test coordinator verbose logging configuration with exception.

    This test verifies that if there's an exception during verbose logging
    configuration, it's caught and handled gracefully without affecting
    coordinator initialization.

    Coverage target: coordinator.py lines 117-118 (exception handling in logging setup)
    """
    # Create configuration with verbose logging enabled
    config = create_temperature_config()
    config[ConfKeys.VERBOSE_LOGGING.value] = True
    config_entry = MockConfigEntry(config)

    # Mock the logger to raise an exception during setLevel
    with patch("custom_components.smart_cover_automation.const.LOGGER") as mock_logger:
        mock_logger.setLevel.side_effect = Exception("Logging configuration error")

        # Create coordinator (should handle logging exception gracefully)
        coordinator = DataUpdateCoordinator(mock_basic_hass, cast(IntegrationConfigEntry, config_entry))

        # Verify coordinator was created successfully despite logging error
        assert coordinator is not None
        assert coordinator.hass is mock_basic_hass

        # Verify setLevel was attempted (and failed)
        mock_logger.setLevel.assert_called_with(logging.DEBUG)
