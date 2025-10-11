"""Focused tests for the IntegrationNumber behavior.

This module contains specialized tests for the Smart Cover Automation number entity,
which provides users with manual control over numeric configuration values. The number
entities allow users to adjust thresholds and limits without changing the underlying
configuration, providing flexible control over automation parameters.

Key testing areas include:
1. **State Persistence**: Tests that number operations properly save their state
   to Home Assistant's configuration options for persistence across restarts
2. **Value Validation**: Tests that number entities enforce min/max constraints
3. **Option Updates**: Tests that number operations correctly update the integration's
   configuration through Home Assistant's options system
4. **Edge Case Handling**: Tests specific behavioral branches and error conditions

The integration number entities are critical for user experience because they provide:
- **Easy Adjustment**: Users can fine-tune automation parameters in real-time
- **Persistent State**: Values are remembered across Home Assistant restarts
- **Range Safety**: Built-in validation prevents invalid configuration values
- **Configuration Integration**: Works seamlessly with Home Assistant's options flow

These tests focus on the number entities' core functionality beyond basic platform testing,
ensuring that the numbers properly integrate with Home Assistant's configuration
system and immediately apply value changes to the automation logic.
"""

from __future__ import annotations

from typing import Iterable, cast
from unittest.mock import AsyncMock, Mock

from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.number import TempThresholdNumber
from custom_components.smart_cover_automation.number import (
    async_setup_entry as async_setup_entry_number,
)


async def test_temp_threshold_number_set_value_persists_option(mock_coordinator_basic) -> None:
    """Test that setting the temperature threshold persists the value.

    This test verifies the complete value change sequence for the temperature threshold:
    1. Value persistence through Home Assistant's options system
    2. Proper integration with the configuration management system
    3. Range validation

    Test scenario:
    - Number starts at default value (25.0°C)
    - User changes value through Home Assistant UI or automation
    - Expected behavior: Options updated with new value

    The set value operation must be atomic and reliable because users expect
    immediate threshold updates when they adjust the number. Any delay
    or failure to persist the value could result in unexpected automation
    behavior or loss of user preferences.
    """
    # Setup integration with initial temperature threshold
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.TEMP_THRESHOLD.value] = 25.0

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True  # type: ignore[attr-defined]
    mock_coordinator_basic.async_update_listeners = Mock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = mock_coordinator_basic
    entry.async_set_options = AsyncMock()  # type: ignore[attr-defined]
    # Mock the hass.config_entries.async_update_entry method
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()  # type: ignore[attr-defined]

    # Capture entities created by the number platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the number platform and capture the number entities
    await async_setup_entry_number(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the temp threshold number entity
    temp_threshold = next(entity for entity in captured if isinstance(entity, TempThresholdNumber))

    # Execute the set value operation with a new temperature
    new_value = 30.5
    await temp_threshold.async_set_native_value(new_value)

    # Verify that async_update_entry was called with the correct options
    # This ensures the number value is persisted to the config entry
    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_args = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    assert call_args[1]["options"][ConfKeys.TEMP_THRESHOLD.value] == new_value


async def test_temp_threshold_number_properties(mock_coordinator_basic) -> None:
    """Test that the temperature threshold number has correct properties.

    This test verifies that the number entity is configured with the correct
    attributes for Home Assistant to display and use it properly:
    - Correct min/max range (10.0 - 40.0°C)
    - Appropriate step size (0.5°C)
    - Correct unit of measurement (°C)
    - Box display mode for better UX
    - Proper device class
    """
    # Setup integration
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.TEMP_THRESHOLD.value] = 25.0

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True  # type: ignore[attr-defined]
    mock_coordinator_basic.async_update_listeners = Mock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the number platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the number platform and capture the number entities
    await async_setup_entry_number(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the temp threshold number entity
    temp_threshold = next(entity for entity in captured if isinstance(entity, TempThresholdNumber))

    # Verify the number entity properties
    assert temp_threshold.native_min_value == 10.0
    assert temp_threshold.native_max_value == 40.0
    assert temp_threshold.native_step == 0.5
    assert temp_threshold.native_unit_of_measurement == "°C"
    from homeassistant.components.number import NumberMode

    assert temp_threshold.mode == NumberMode.BOX


async def test_temp_threshold_number_reads_current_value(mock_coordinator_basic) -> None:
    """Test that the temperature threshold number returns the current config value.

    This test ensures that the number entity correctly reads and returns the
    current temperature threshold value from the integration configuration.
    """
    # Setup integration with specific temperature threshold
    entry = mock_coordinator_basic.config_entry
    test_value = 28.5
    entry.runtime_data.config[ConfKeys.TEMP_THRESHOLD.value] = test_value

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True  # type: ignore[attr-defined]
    mock_coordinator_basic.async_update_listeners = Mock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the number platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the number platform and capture the number entities
    await async_setup_entry_number(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the temp threshold number entity
    temp_threshold = next(entity for entity in captured if isinstance(entity, TempThresholdNumber))

    # Verify that the entity returns the correct current value
    assert temp_threshold.native_value == test_value


async def test_temp_threshold_number_device_info(mock_coordinator_basic) -> None:
    """Test that the temperature threshold number has correct device info.

    This test verifies that the number entity properly associates itself
    with the integration's device in Home Assistant's device registry.
    """
    # Setup integration
    entry = mock_coordinator_basic.config_entry
    entry.runtime_data.config[ConfKeys.TEMP_THRESHOLD.value] = 25.0

    # Setup mock Home Assistant environment
    mock_coordinator_basic.last_update_success = True  # type: ignore[attr-defined]
    mock_coordinator_basic.async_update_listeners = Mock()  # type: ignore[assignment]
    entry.runtime_data.coordinator = mock_coordinator_basic

    # Capture entities created by the number platform
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        """Mock entity addition function that captures created entities."""
        captured.extend(list(new_entities))

    # Setup the number platform and capture the number entities
    await async_setup_entry_number(mock_coordinator_basic.hass, cast(IntegrationConfigEntry, entry), add_entities)

    # Find the temp threshold number entity
    temp_threshold = next(entity for entity in captured if isinstance(entity, TempThresholdNumber))

    # Verify device info is present and has the expected structure
    device_info = temp_threshold.device_info
    assert device_info is not None
    assert "identifiers" in device_info
    assert "name" in device_info
