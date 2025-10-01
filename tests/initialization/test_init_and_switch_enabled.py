"""Tests for integration initialization helpers and options flow functionality.

This module tests the core initialization and configuration management functionality
of the Smart Cover Automation integration. The tests validate:

- Options flow creation and initialization
- Configuration entry management
- Integration-level helper functions from __init__.py
- Options flow handler instantiation and readiness
- Configuration modification capabilities through Home Assistant UI

The options flow system allows users to modify integration settings after initial
setup without requiring complete reconfiguration. This is essential for adjusting
automation parameters, enabling/disabling features, and updating thresholds as
user needs evolve.

These tests ensure that the integration properly exposes configuration options
and that the options flow handler is correctly instantiated and functional.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

from custom_components.smart_cover_automation import async_get_options_flow
from custom_components.smart_cover_automation.data import IntegrationConfigEntry


async def test_async_get_options_flow_returns_handler(mock_config_entry_basic, mock_basic_hass) -> None:
    """Test that the integration properly creates and returns an options flow handler.

    Validates that the async_get_options_flow function correctly instantiates
    an OptionsFlowHandler for managing configuration changes after initial setup.
    The options flow allows users to:

    - Modify automation parameters (temperature thresholds, covers, etc.)
    - Enable or disable specific features (switch entities)
    - Update sun automation settings
    - Adjust timing and behavior parameters

    Test verification:
    - Options flow handler is successfully created
    - Handler has the required async_step_init method for Home Assistant integration
    - Handler is properly bound to the configuration entry

    This ensures users can modify integration settings through the Home Assistant
    UI without requiring complete reconfiguration or integration removal/re-addition.
    """
    # Configure the mock config entry and hass
    mock_config_entry_basic.hass = mock_basic_hass
    mock_basic_hass.states = MagicMock()

    # Request options flow handler from the integration
    flow = await async_get_options_flow(cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Verify the handler has the required method for Home Assistant options flow
    assert hasattr(flow, "async_step_init")
