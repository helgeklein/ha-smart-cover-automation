"""Tests for TempThresholdNumber entity.

This module contains tests for the TempThresholdNumber entity, which provides
a UI control for users to adjust the temperature threshold for heat protection.

Coverage target: number.py lines 57-189 (IntegrationNumber and TempThresholdNumber classes)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast
from unittest.mock import Mock

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import DOMAIN, NUMBER_KEY_TEMP_THRESHOLD
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.number import TempThresholdNumber, async_setup_entry

if TYPE_CHECKING:
    pass


async def test_temp_threshold_number_entity_properties(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test TempThresholdNumber entity properties.

    Verifies that the TempThresholdNumber entity is properly initialized with:
    - Correct entity description
    - Proper translation key
    - Icon
    - Entity category
    - Temperature device class
    - Min/max values and step
    - Unit of measurement

    Coverage target: number.py lines 164-189
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Capture entities
    captured: list[Entity] = []

    def add_entities(new_entities: Iterable[Entity], update_before_add: bool = False) -> None:  # noqa: ARG001
        captured.extend(list(new_entities))

    # Setup the number platform
    await async_setup_entry(
        mock_hass_with_spec,
        cast(IntegrationConfigEntry, mock_config_entry_basic),
        add_entities,
    )

    # Get the temp threshold number entity (it's the sixth entity now)
    temp_threshold_number = captured[5]
    assert isinstance(temp_threshold_number, TempThresholdNumber)

    # Verify device class
    from homeassistant.components.number import NumberDeviceClass

    assert temp_threshold_number.entity_description.device_class == NumberDeviceClass.TEMPERATURE

    # Verify entity description properties
    assert temp_threshold_number.entity_description.key == NUMBER_KEY_TEMP_THRESHOLD
    assert temp_threshold_number.entity_description.translation_key == NUMBER_KEY_TEMP_THRESHOLD
    assert temp_threshold_number.entity_description.icon == "mdi:thermometer-lines"
    assert temp_threshold_number.entity_description.entity_category == EntityCategory.CONFIG

    # Verify unique_id format
    assert temp_threshold_number.unique_id == f"{DOMAIN}_{NUMBER_KEY_TEMP_THRESHOLD}"

    # Verify numeric properties
    assert temp_threshold_number.entity_description.native_min_value == 10
    assert temp_threshold_number.entity_description.native_max_value == 40
    assert temp_threshold_number.entity_description.native_step == 0.5
    assert temp_threshold_number.entity_description.mode == NumberMode.BOX
    assert temp_threshold_number.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS


async def test_temp_threshold_number_native_value_returns_config_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that native_value property returns the configured temperature threshold.

    Verifies that the number entity correctly reads the current temperature
    threshold from the resolved configuration.

    Coverage target: number.py lines 115-123
    """
    # Set temperature threshold in config entry options
    mock_config_entry_basic.options[ConfKeys.TEMP_THRESHOLD.value] = 28.5

    # Create coordinator with specific temp threshold
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    temp_threshold_number = TempThresholdNumber(coordinator)

    # Verify that native_value returns the configured temp threshold
    assert temp_threshold_number.native_value == 28.5


async def test_temp_threshold_number_native_value_with_different_values(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test native_value with various temperature threshold values.

    Coverage target: number.py lines 115-123
    """
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    temp_threshold_number = TempThresholdNumber(coordinator)

    # Test various temperature values
    test_values = [10.0, 15.5, 24.0, 30.5, 40.0]

    for value in test_values:
        mock_config_entry_basic.options[ConfKeys.TEMP_THRESHOLD.value] = value
        # Force re-resolution of config
        coordinator._merged_config = dict(mock_config_entry_basic.options)
        assert temp_threshold_number.native_value == value


async def test_temp_threshold_number_async_set_native_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that async_set_native_value updates the temperature threshold.

    Verifies that setting a new value through the number entity updates
    the configuration and triggers the appropriate update flow.

    Coverage target: number.py lines 125-137
    """
    # Set initial temperature threshold
    mock_config_entry_basic.options[ConfKeys.TEMP_THRESHOLD.value] = 24.0

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    temp_threshold_number = TempThresholdNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new temperature threshold value
    new_value = 30.0
    await temp_threshold_number.async_set_native_value(new_value)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify it was called with the correct entry
    call_args = mock_update.call_args
    assert call_args[0][0] == mock_config_entry_basic

    # Verify the options were updated correctly
    updated_options = call_args[1]["options"]
    assert updated_options[ConfKeys.TEMP_THRESHOLD.value] == new_value


async def test_temp_threshold_number_async_set_native_value_preserves_other_options(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that async_set_native_value preserves other configuration options.

    Verifies that when updating the temperature threshold, all other
    configuration options remain unchanged.

    Coverage target: number.py lines 125-137, 139-161
    """
    # Set multiple options in config entry
    mock_config_entry_basic.options[ConfKeys.TEMP_THRESHOLD.value] = 24.0
    mock_config_entry_basic.options[ConfKeys.ENABLED.value] = True
    mock_config_entry_basic.options[ConfKeys.SIMULATION_MODE.value] = False
    mock_config_entry_basic.options["some_other_key"] = "some_value"

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    temp_threshold_number = TempThresholdNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new temperature threshold value
    new_value = 32.5
    await temp_threshold_number.async_set_native_value(new_value)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify the options were updated correctly
    updated_options = mock_update.call_args[1]["options"]
    assert updated_options[ConfKeys.TEMP_THRESHOLD.value] == new_value
    assert updated_options[ConfKeys.ENABLED.value] is True
    assert updated_options[ConfKeys.SIMULATION_MODE.value] is False
    assert updated_options["some_other_key"] == "some_value"


async def test_temp_threshold_number_availability(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that TempThresholdNumber availability tracks coordinator status.

    Verifies that the number entity's availability is linked to the
    coordinator's last_update_success status.

    Coverage target: number.py lines 57-110 (inherited availability from IntegrationEntity)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    temp_threshold_number = TempThresholdNumber(coordinator)

    # Test when coordinator has successful updates
    coordinator.last_update_success = True
    assert temp_threshold_number.available is True

    # Test when coordinator has failed updates
    coordinator.last_update_success = False
    assert temp_threshold_number.available is False


async def test_temp_threshold_number_translation_key_set(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that TempThresholdNumber has translation_key properly set.

    Verifies that the translation_key is set, which is required for
    Home Assistant to properly localize the entity name.

    Coverage target: number.py lines 164-189
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    temp_threshold_number = TempThresholdNumber(coordinator)

    # Verify translation_key is set
    assert temp_threshold_number.entity_description.translation_key == NUMBER_KEY_TEMP_THRESHOLD
    assert temp_threshold_number.entity_description.translation_key is not None


async def test_temp_threshold_number_config_key_storage(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that TempThresholdNumber properly stores the config key.

    Verifies that the config key is stored correctly and can be used
    to read and update the configuration.

    Coverage target: number.py lines 76-107
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    temp_threshold_number = TempThresholdNumber(coordinator)

    # Verify the internal config key is set correctly
    assert temp_threshold_number._config_key == ConfKeys.TEMP_THRESHOLD.value


async def test_temp_threshold_number_boundary_values(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test TempThresholdNumber with boundary values.

    Verifies that the number entity correctly handles minimum and maximum
    temperature values.

    Coverage target: number.py lines 115-123
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    temp_threshold_number = TempThresholdNumber(coordinator)

    # Test minimum value
    mock_config_entry_basic.options[ConfKeys.TEMP_THRESHOLD.value] = 10.0
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert temp_threshold_number.native_value == 10.0

    # Test maximum value
    mock_config_entry_basic.options[ConfKeys.TEMP_THRESHOLD.value] = 40.0
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert temp_threshold_number.native_value == 40.0

    # Test mid-range value
    mock_config_entry_basic.options[ConfKeys.TEMP_THRESHOLD.value] = 25.5
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert temp_threshold_number.native_value == 25.5


async def test_async_persist_option_triggers_update_listener(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that _async_persist_option triggers the update listener.

    Verifies that updating an option through the number entity will
    trigger the smart reload listener in __init__.py, which decides
    whether to do a full reload or just refresh the coordinator.

    Coverage target: number.py lines 139-161
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    temp_threshold_number = TempThresholdNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Call _async_persist_option directly
    await temp_threshold_number._async_persist_option(ConfKeys.TEMP_THRESHOLD.value, 35.0)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify the entry was passed correctly
    assert mock_update.call_args[0][0] == mock_config_entry_basic

    # Verify the new value is in the options
    updated_options = mock_update.call_args[1]["options"]
    assert updated_options[ConfKeys.TEMP_THRESHOLD.value] == 35.0
