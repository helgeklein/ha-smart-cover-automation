"""Parameterized tests for all Number entities.

This module contains comprehensive tests for all number entities in the integration,
using parameterization to avoid code duplication while maintaining thorough coverage.

Coverage target: number.py (all number entity classes)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, cast
from unittest.mock import Mock

import pytest
from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    NUMBER_KEY_COVERS_MAX_CLOSURE,
    NUMBER_KEY_COVERS_MIN_CLOSURE,
    NUMBER_KEY_MANUAL_OVERRIDE_DURATION,
    NUMBER_KEY_SUN_AZIMUTH_TOLERANCE,
    NUMBER_KEY_SUN_ELEVATION_THRESHOLD,
    NUMBER_KEY_TEMP_THRESHOLD,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.number import (
    CoversMaxClosureNumber,
    CoversMinClosureNumber,
    ManualOverrideDurationNumber,
    SunAzimuthToleranceNumber,
    SunElevationThresholdNumber,
    TempThresholdNumber,
    async_setup_entry,
)

if TYPE_CHECKING:
    pass


# Entity configuration for parameterized tests
ENTITY_CONFIGS = [
    {
        "id": "covers_max_closure",
        "class": CoversMaxClosureNumber,
        "key": NUMBER_KEY_COVERS_MAX_CLOSURE,
        "config_key": ConfKeys.COVERS_MAX_CLOSURE.value,
        "translation_key": NUMBER_KEY_COVERS_MAX_CLOSURE,
        "icon": "mdi:window-shutter",
        "entity_category": EntityCategory.CONFIG,
        "device_class": None,
        "min_value": 0,
        "max_value": 100,
        "step": 1,
        "mode": NumberMode.BOX,
        "unit": "%",
        "default_value": 0.0,
        "test_values": [0, 10, 25, 50, 75, 100],
        "boundary_min": 0,
        "boundary_max": 100,
        "entity_index": 0,  # Position in async_setup_entry list
        "has_conversion": False,  # No unit conversion needed
    },
    {
        "id": "covers_min_closure",
        "class": CoversMinClosureNumber,
        "key": NUMBER_KEY_COVERS_MIN_CLOSURE,
        "config_key": ConfKeys.COVERS_MIN_CLOSURE.value,
        "translation_key": NUMBER_KEY_COVERS_MIN_CLOSURE,
        "icon": "mdi:window-shutter-open",
        "entity_category": EntityCategory.CONFIG,
        "device_class": None,
        "min_value": 0,
        "max_value": 100,
        "step": 1,
        "mode": NumberMode.BOX,
        "unit": "%",
        "default_value": 100.0,
        "test_values": [0, 10, 25, 50, 75, 100],
        "boundary_min": 0,
        "boundary_max": 100,
        "entity_index": 1,
        "has_conversion": False,
    },
    {
        "id": "manual_override_duration",
        "class": ManualOverrideDurationNumber,
        "key": NUMBER_KEY_MANUAL_OVERRIDE_DURATION,
        "config_key": ConfKeys.MANUAL_OVERRIDE_DURATION.value,
        "translation_key": NUMBER_KEY_MANUAL_OVERRIDE_DURATION,
        "icon": "mdi:timer-outline",
        "entity_category": EntityCategory.CONFIG,
        "device_class": None,
        "min_value": 0,
        "max_value": None,  # Unlimited
        "step": 1,
        "mode": NumberMode.BOX,
        "unit": UnitOfTime.MINUTES,
        "default_value": 30.0,  # 30 minutes (stored as 1800 seconds)
        "test_values": [(0, 0.0), (60, 1.0), (300, 5.0), (1800, 30.0), (3600, 60.0), (7200, 120.0)],  # (seconds, minutes)
        "boundary_min": 0,
        "boundary_max": 86400,  # 24 hours in seconds
        "boundary_max_displayed": 1440.0,  # 24 hours in minutes
        "entity_index": 2,
        "has_conversion": True,  # Converts seconds to/from minutes
        "conversion_factor": 60,
    },
    {
        "id": "sun_azimuth_tolerance",
        "class": SunAzimuthToleranceNumber,
        "key": NUMBER_KEY_SUN_AZIMUTH_TOLERANCE,
        "config_key": ConfKeys.SUN_AZIMUTH_TOLERANCE.value,
        "translation_key": NUMBER_KEY_SUN_AZIMUTH_TOLERANCE,
        "icon": "mdi:sun-compass",
        "entity_category": EntityCategory.CONFIG,
        "device_class": None,
        "min_value": 0,
        "max_value": 180,
        "step": 1,
        "mode": NumberMode.BOX,
        "unit": "°",
        "default_value": 90.0,
        "test_values": [0, 20, 45, 90, 135, 180],
        "boundary_min": 0,
        "boundary_max": 180,
        "entity_index": 3,
        "has_conversion": False,
    },
    {
        "id": "sun_elevation_threshold",
        "class": SunElevationThresholdNumber,
        "key": NUMBER_KEY_SUN_ELEVATION_THRESHOLD,
        "config_key": ConfKeys.SUN_ELEVATION_THRESHOLD.value,
        "translation_key": NUMBER_KEY_SUN_ELEVATION_THRESHOLD,
        "icon": "mdi:sun-angle-outline",
        "entity_category": EntityCategory.CONFIG,
        "device_class": None,
        "min_value": 0,
        "max_value": 90,
        "step": 1,
        "mode": NumberMode.BOX,
        "unit": "°",
        "default_value": 10.0,
        "test_values": [0, 10, 30, 45, 60, 90],
        "boundary_min": 0,
        "boundary_max": 90,
        "entity_index": 4,
        "has_conversion": False,
    },
    {
        "id": "temp_threshold",
        "class": TempThresholdNumber,
        "key": NUMBER_KEY_TEMP_THRESHOLD,
        "config_key": ConfKeys.TEMP_THRESHOLD.value,
        "translation_key": NUMBER_KEY_TEMP_THRESHOLD,
        "icon": "mdi:thermometer-lines",
        "entity_category": EntityCategory.CONFIG,
        "device_class": NumberDeviceClass.TEMPERATURE,
        "min_value": -100,
        "max_value": 100,
        "step": 0.5,
        "mode": NumberMode.BOX,
        "unit": UnitOfTemperature.CELSIUS,
        "default_value": 24.0,
        "test_values": [-100.0, -10.0, 0.0, 24.0, 50.0, 100.0],
        "boundary_min": -100.0,
        "boundary_max": 100.0,
        "entity_index": 5,
        "has_conversion": False,
    },
]


#
# test_number_entity_properties
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_properties(mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]) -> None:
    """Test that number entity has correct properties.

    Verifies that the number entity is properly initialized with:
    - Correct entity description
    - Proper translation key
    - Icon
    - Entity category
    - Min/max values and step
    - Unit of measurement
    - Device class (if applicable)

    Coverage target: number.py (all number entity classes)
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

    # Get the entity by index
    entity = captured[entity_config["entity_index"]]
    assert isinstance(entity, entity_config["class"])

    # Verify entity description properties
    assert entity.entity_description.key == entity_config["key"]
    assert entity.entity_description.translation_key == entity_config["translation_key"]
    assert entity.entity_description.icon == entity_config["icon"]
    assert entity.entity_description.entity_category == entity_config["entity_category"]

    # Verify device class if specified
    if entity_config["device_class"] is not None:
        assert entity.entity_description.device_class == entity_config["device_class"]

    # Verify unique_id format
    assert entity.unique_id == f"{mock_config_entry_basic.entry_id}_{entity_config['key']}"

    # Verify numeric properties
    assert entity.entity_description.native_min_value == entity_config["min_value"]
    assert entity.entity_description.native_max_value == entity_config["max_value"]
    assert entity.entity_description.native_step == entity_config["step"]
    assert entity.entity_description.mode == entity_config["mode"]
    assert entity.entity_description.native_unit_of_measurement == entity_config["unit"]


#
# test_number_entity_native_value_returns_config_value
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_native_value_returns_config_value(
    mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]
) -> None:
    """Test that native_value property returns the configured value.

    Verifies that the number entity correctly reads the current value
    from the resolved configuration, with unit conversion if applicable.

    Coverage target: number.py lines 115-123
    """
    # Set value in config entry options
    if entity_config["has_conversion"]:
        # For entities with conversion (e.g., manual override duration: seconds -> minutes)
        test_value_stored = 3600  # 60 minutes in seconds
        expected_displayed = 60.0  # Displayed as 60 minutes
    else:
        # For entities without conversion
        test_value_stored = 25 if entity_config["step"] == 1 else 28.5
        expected_displayed = float(test_value_stored)

    mock_config_entry_basic.options[entity_config["config_key"]] = test_value_stored

    # Create coordinator with specific value
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Verify that native_value returns the configured value (with conversion if applicable)
    assert entity.native_value == expected_displayed


#
# test_number_entity_native_value_with_different_values
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_native_value_with_different_values(
    mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]
) -> None:
    """Test native_value with various values.

    Coverage target: number.py lines 115-123
    """
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    entity = entity_config["class"](coordinator)

    # Test various values
    test_values = entity_config["test_values"]

    for test_case in test_values:
        if entity_config["has_conversion"]:
            # For entities with conversion, test_values are tuples: (stored_value, displayed_value)
            stored_value, expected_value = test_case
        else:
            # For entities without conversion, test_values are simple values
            stored_value = test_case
            expected_value = float(test_case)

        mock_config_entry_basic.options[entity_config["config_key"]] = stored_value
        # Force re-resolution of config
        coordinator._merged_config = dict(mock_config_entry_basic.options)
        assert entity.native_value == expected_value


#
# test_number_entity_async_set_native_value
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_async_set_native_value(mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]) -> None:
    """Test that async_set_native_value updates the configuration.

    Verifies that setting a new value through the number entity updates
    the configuration and triggers the appropriate update flow, with
    unit conversion if applicable.

    Coverage target: number.py lines 125-137
    """
    # Set initial value
    if entity_config["has_conversion"]:
        initial_stored = 1800  # 30 minutes in seconds
        new_displayed = 45.0  # 45 minutes
        expected_stored = 2700  # 45 * 60 seconds
    else:
        initial_stored = entity_config["boundary_min"]
        new_displayed = 50.0 if entity_config["step"] == 1 else 30.0
        expected_stored = new_displayed

    mock_config_entry_basic.options[entity_config["config_key"]] = initial_stored

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new value
    await entity.async_set_native_value(new_displayed)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify it was called with the correct entry
    call_args = mock_update.call_args
    assert call_args[0][0] == mock_config_entry_basic

    # Verify the options were updated correctly (with conversion if applicable)
    updated_options = call_args[1]["options"]
    assert updated_options[entity_config["config_key"]] == expected_stored


#
# test_number_entity_async_set_native_value_preserves_other_options
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_async_set_native_value_preserves_other_options(
    mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]
) -> None:
    """Test that async_set_native_value preserves other configuration options.

    Verifies that when updating the value, all other configuration
    options remain unchanged.

    Coverage target: number.py lines 125-137, 139-161
    """
    # Set multiple options in config entry
    if entity_config["has_conversion"]:
        initial_value = 1800
        new_value = 60.0  # 60 minutes
        expected_stored = 3600  # 60 * 60 seconds
    else:
        initial_value = entity_config["boundary_min"]
        new_value = 75.0 if entity_config["step"] == 1 else 32.5
        expected_stored = new_value

    mock_config_entry_basic.options[entity_config["config_key"]] = initial_value
    mock_config_entry_basic.options[ConfKeys.ENABLED.value] = True
    mock_config_entry_basic.options[ConfKeys.SIMULATION_MODE.value] = False
    mock_config_entry_basic.options["some_other_key"] = "some_value"

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new value
    await entity.async_set_native_value(new_value)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify the options were updated correctly
    updated_options = mock_update.call_args[1]["options"]
    assert updated_options[entity_config["config_key"]] == expected_stored
    assert updated_options[ConfKeys.ENABLED.value] is True
    assert updated_options[ConfKeys.SIMULATION_MODE.value] is False
    assert updated_options["some_other_key"] == "some_value"


#
# test_number_entity_availability
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_availability(mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]) -> None:
    """Test that number entity availability tracks coordinator status.

    Verifies that the number entity's availability is linked to the
    coordinator's last_update_success status.

    Coverage target: number.py lines 57-110 (inherited availability from IntegrationEntity)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Test when coordinator reports success
    coordinator.last_update_success = True
    assert entity.available is True

    # Test when coordinator reports failure
    coordinator.last_update_success = False
    assert entity.available is False


#
# test_number_entity_translation_key_set
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_translation_key_set(mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]) -> None:
    """Test that number entity has translation_key properly set.

    Verifies that the translation_key is set, which is required for
    Home Assistant to properly localize the entity name.

    Coverage target: number.py (all number entity classes)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Verify translation_key is set
    assert entity.entity_description.translation_key == entity_config["translation_key"]
    assert entity.entity_description.translation_key is not None


#
# test_number_entity_config_key_storage
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_config_key_storage(mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]) -> None:
    """Test that number entity properly stores the config key.

    Verifies that the config key is stored correctly and can be used
    to read and update the configuration.

    Coverage target: number.py lines 76-107
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Verify the internal config key is set correctly
    assert entity._config_key == entity_config["config_key"]


#
# test_number_entity_boundary_values
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_boundary_values(mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]) -> None:
    """Test number entity with boundary values.

    Verifies that the number entity correctly handles minimum and maximum
    values according to its specification, with unit conversion if applicable.

    Coverage target: number.py lines 115-123
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Test minimum boundary value
    mock_config_entry_basic.options[entity_config["config_key"]] = entity_config["boundary_min"]
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    if entity_config["has_conversion"]:
        expected_min = entity_config["boundary_min"] / entity_config["conversion_factor"]
    else:
        expected_min = float(entity_config["boundary_min"])
    assert entity.native_value == expected_min

    # Test maximum boundary value (if not unlimited)
    if entity_config["boundary_max"] is not None:
        mock_config_entry_basic.options[entity_config["config_key"]] = entity_config["boundary_max"]
        coordinator._merged_config = dict(mock_config_entry_basic.options)
        if entity_config["has_conversion"]:
            expected_max = entity_config["boundary_max_displayed"]
        else:
            expected_max = float(entity_config["boundary_max"])
        assert entity.native_value == expected_max


#
# test_number_entity_default_value
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_default_value(mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]) -> None:
    """Test number entity with default configuration.

    Verifies that when no explicit value is configured, the number entity
    uses the default value from the configuration specification.

    Coverage target: number.py lines 115-123
    """
    # Don't set any explicit value in config entry options
    # Should use default from config specs

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Verify that native_value returns the default value
    assert entity.native_value == entity_config["default_value"]


#
# test_number_entity_persist_option_triggers_update_listener
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_persist_option_triggers_update_listener(
    mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]
) -> None:
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
    entity = entity_config["class"](coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Determine test value
    if entity_config["has_conversion"]:
        test_value_to_store = 4200  # 70 minutes in seconds
    else:
        test_value_to_store = 35.0 if entity_config["step"] == 0.5 else 50

    # Call _async_persist_option directly
    await entity._async_persist_option(entity_config["config_key"], test_value_to_store)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify the entry was passed correctly
    assert mock_update.call_args[0][0] == mock_config_entry_basic

    # Verify the new value is in the options
    updated_options = mock_update.call_args[1]["options"]
    assert updated_options[entity_config["config_key"]] == test_value_to_store


#
# test_number_entity_coordinator_property
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_coordinator_property(mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]) -> None:
    """Test that number entity has proper coordinator reference.

    Verifies that the number entity maintains a reference to its coordinator,
    which is essential for accessing configuration and triggering updates.

    Coverage target: number.py (IntegrationNumber base class)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Verify coordinator property
    assert entity.coordinator is coordinator


#
# test_number_entity_device_info_links_to_integration
#
@pytest.mark.parametrize("entity_config", ENTITY_CONFIGS, ids=[cfg["id"] for cfg in ENTITY_CONFIGS])
async def test_number_entity_device_info_links_to_integration(
    mock_hass_with_spec, mock_config_entry_basic, entity_config: dict[str, Any]
) -> None:
    """Test that number entity is properly linked to the integration device.

    Verifies that the number entity appears under the correct device in
    the Home Assistant UI, enabling proper organization and management.

    Coverage target: number.py (IntegrationNumber base class via IntegrationEntity)
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    entity = entity_config["class"](coordinator)

    # Verify device_info is properly configured
    device_info = entity.device_info
    assert device_info is not None
    assert ("identifiers" in device_info) or ("name" in device_info)
