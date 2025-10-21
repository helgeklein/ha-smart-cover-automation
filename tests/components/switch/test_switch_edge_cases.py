"""Edge case tests for the switch platform.

This module tests specific edge cases and behavioral branches for the Smart Cover
Automation switch entity that require special test conditions or parameter variations.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.switch import EnabledSwitch, VerboseLoggingSwitch


@pytest.mark.parametrize(
    "last_update_success, expected_availability",
    [
        (True, True),  # Successful update should be available
        (False, False),  # Failed update should be unavailable
    ],
)
async def test_switch_availability_property_delegation(mock_coordinator_basic, last_update_success, expected_availability) -> None:
    """Test switch availability property delegation to parent classes.

    This parametrized test verifies that the switch's availability property properly
    delegates to parent class implementations based on coordinator update status.

    Coverage target: switch.py line 100 (availability property override)
    """
    # Set coordinator update status
    mock_coordinator_basic.last_update_success = last_update_success

    # Create enabled switch instance directly
    switch = EnabledSwitch(mock_coordinator_basic)

    # Test that availability property delegates to parent and reflects update status
    availability = switch.available

    # Verify that the property delegation works and returns expected availability
    assert availability == expected_availability
    assert isinstance(availability, bool)


@pytest.mark.parametrize(
    "enabled_config_value, expected_is_on",
    [
        (True, True),  # Enabled configuration should return True
        (False, False),  # Disabled configuration should return False
        (1, True),  # Truthy integer should return True
        (0, False),  # Falsy integer should return False
        ("true", True),  # String 'true' should be converted to True
        ("false", False),  # String 'false' should be converted to False
        ("True", True),  # String 'True' should be converted to True
        ("False", False),  # String 'False' should be converted to False
        ("yes", True),  # String 'yes' should be converted to True
        ("no", False),  # String 'no' should be converted to False
        ("on", True),  # String 'on' should be converted to True
        ("off", False),  # String 'off' should be converted to False
        ("1", True),  # String '1' should be converted to True
        ("0", False),  # String '0' should be converted to False
        ("anything", True),  # Other non-empty strings should be truthy
        ("", False),  # Empty string should be falsy
    ],
)
async def test_switch_is_on_property_with_config_resolution(
    mock_coordinator_basic, enabled_config_value: Any, expected_is_on: bool
) -> None:
    """Test switch is_on property with various configuration values.

    This parametrized test verifies that the switch's is_on property properly resolves
    different types of configuration values and returns the correct enabled state.

    Coverage target: switch.py line 110 (is_on property with resolve_entry call)
    """
    # Set the enabled configuration value in options
    mock_coordinator_basic.config_entry.data = {}
    mock_coordinator_basic.config_entry.options = {ConfKeys.ENABLED.value: enabled_config_value}

    # Create enabled switch instance directly
    switch = EnabledSwitch(mock_coordinator_basic)

    # Test that is_on property accesses resolved configuration
    is_on_state = switch.is_on

    # Verify that the property returns the expected configuration enabled state
    assert isinstance(is_on_state, bool)
    assert is_on_state == expected_is_on


@pytest.mark.parametrize(
    "config_verbose_logging, logger_level, expected_is_on, test_description",
    [
        # Config False, Logger INFO -> False (both disabled)
        (False, logging.INFO, False, "config off, logger info -> off"),
        # Config False, Logger DEBUG -> True (logger enables it)
        (False, logging.DEBUG, True, "config off, logger debug -> on"),
        # Config True, Logger INFO -> True (config enables it)
        (True, logging.INFO, True, "config on, logger info -> on"),
        # Config True, Logger DEBUG -> True (both enabled)
        (True, logging.DEBUG, True, "config on, logger debug -> on"),
        # Config False, Logger WARNING -> False (both disabled)
        (False, logging.WARNING, False, "config off, logger warning -> off"),
        # Config True, Logger WARNING -> True (config enables it)
        (True, logging.WARNING, True, "config on, logger warning -> on"),
        # Config False, Logger ERROR -> False (both disabled)
        (False, logging.ERROR, False, "config off, logger error -> off"),
        # Config True, Logger ERROR -> True (config enables it)
        (True, logging.ERROR, True, "config on, logger error -> on"),
    ],
)
async def test_verbose_logging_switch_checks_ha_logger_level(
    mock_coordinator_basic, config_verbose_logging: bool, logger_level: int, expected_is_on: bool, test_description: str
) -> None:
    """Test VerboseLoggingSwitch.is_on checks both config and Home Assistant logger level.

    This test verifies that the verbose logging switch properly reflects the actual
    logging state by checking both:
    1. The integration's verbose_logging configuration option
    2. Home Assistant's logger level for the integration

    The switch should return True if EITHER the config is True OR the logger is set
    to DEBUG level, allowing users to enable debug logging via configuration.yaml's
    logger section and have the switch reflect that state.

    Coverage target: switch.py VerboseLoggingSwitch.is_on property
    """
    # Setup configuration with verbose_logging value in options
    mock_coordinator_basic.config_entry.data = {}
    mock_coordinator_basic.config_entry.options = {
        ConfKeys.COVERS.value: ["cover.test"],
        ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        ConfKeys.VERBOSE_LOGGING.value: config_verbose_logging,
    }

    # Get the integration's logger and set its level
    integration_logger = logging.getLogger("custom_components.smart_cover_automation")
    original_level = integration_logger.level
    try:
        integration_logger.setLevel(logger_level)

        # Create verbose logging switch
        switch = VerboseLoggingSwitch(mock_coordinator_basic)

        # Test the is_on property
        is_on_state = switch.is_on

        # Verify the result matches expectations
        assert isinstance(is_on_state, bool), f"is_on should return bool for: {test_description}"
        assert is_on_state == expected_is_on, (
            f"Failed for: {test_description}\n"
            f"  config_verbose_logging: {config_verbose_logging}\n"
            f"  logger_level: {logging.getLevelName(logger_level)}\n"
            f"  logger.isEnabledFor(DEBUG): {integration_logger.isEnabledFor(logging.DEBUG)}\n"
            f"  expected: {expected_is_on}, got: {is_on_state}"
        )
    finally:
        # Restore original logger level to avoid affecting other tests
        integration_logger.setLevel(original_level)
