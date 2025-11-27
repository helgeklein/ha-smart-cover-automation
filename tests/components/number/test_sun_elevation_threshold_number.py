"""Tests for SunElevationThresholdNumber entity.

This module contains tests for the SunElevationThresholdNumber entity, which provides
a UI control for users to adjust the sun elevation threshold.

Coverage target: number.py SunElevationThresholdNumber class
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast
from unittest.mock import AsyncMock

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import DOMAIN, NUMBER_KEY_SUN_ELEVATION_THRESHOLD
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.number import SunElevationThresholdNumber, async_setup_entry

if TYPE_CHECKING:
    pass


async def test_sun_elevation_threshold_number_entity_properties(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test SunElevationThresholdNumber entity properties.

    Verifies that the SunElevationThresholdNumber entity is properly initialized with:
    - Correct entity description
    - Proper translation key
    - Icon
    - Entity category
    - Min/max values and step
    - Unit of measurement
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

    # Get the sun elevation threshold number entity (it's the fourth entity now)
    sun_elevation_threshold_number = captured[3]
    assert isinstance(sun_elevation_threshold_number, SunElevationThresholdNumber)

    # Verify entity description properties
    assert sun_elevation_threshold_number.entity_description.key == NUMBER_KEY_SUN_ELEVATION_THRESHOLD
    assert sun_elevation_threshold_number.entity_description.translation_key == NUMBER_KEY_SUN_ELEVATION_THRESHOLD
    assert sun_elevation_threshold_number.entity_description.icon == "mdi:angle-acute"
    assert sun_elevation_threshold_number.entity_description.entity_category == EntityCategory.CONFIG

    # Verify unique_id format
    assert sun_elevation_threshold_number.unique_id == f"{DOMAIN}_{NUMBER_KEY_SUN_ELEVATION_THRESHOLD}"

    # Verify numeric properties
    assert sun_elevation_threshold_number.entity_description.native_min_value == 0
    assert sun_elevation_threshold_number.entity_description.native_max_value == 90
    assert sun_elevation_threshold_number.entity_description.native_step == 1
    assert sun_elevation_threshold_number.entity_description.mode == NumberMode.BOX
    assert sun_elevation_threshold_number.entity_description.native_unit_of_measurement == "°"


async def test_sun_elevation_threshold_number_native_value_returns_config_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that native_value property returns the configured sun elevation threshold.

    Verifies that the number entity correctly reads the current sun elevation
    threshold from the resolved configuration.
    """
    # Set sun elevation threshold in config entry options
    mock_config_entry_basic.options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] = 15.0

    # Create coordinator with specific sun elevation threshold
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    sun_elevation_threshold_number = SunElevationThresholdNumber(coordinator)

    # Verify that native_value returns the configured sun elevation threshold
    assert sun_elevation_threshold_number.native_value == 15.0


async def test_sun_elevation_threshold_number_native_value_with_different_values(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test native_value with various sun elevation threshold values."""
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    sun_elevation_threshold_number = SunElevationThresholdNumber(coordinator)

    # Test various sun elevation values
    test_values = [0.0, 10.0, 30.0, 45.0, 90.0]

    for value in test_values:
        mock_config_entry_basic.options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] = value
        # Force re-resolution of config
        coordinator._merged_config = dict(mock_config_entry_basic.options)
        assert sun_elevation_threshold_number.native_value == value


async def test_sun_elevation_threshold_number_async_set_native_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that async_set_native_value updates the sun elevation threshold.

    Verifies that setting a new value through the number entity updates
    the configuration and triggers the appropriate update flow.
    """
    # Set initial sun elevation threshold
    mock_config_entry_basic.options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] = 10.0

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    sun_elevation_threshold_number = SunElevationThresholdNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = AsyncMock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new sun elevation threshold value
    new_value = 25.0
    await sun_elevation_threshold_number.async_set_native_value(new_value)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify it was called with the correct entry
    call_args = mock_update.call_args
    assert call_args[0][0] == mock_config_entry_basic

    # Verify the options were updated correctly
    updated_options = call_args[1]["options"]
    assert updated_options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == new_value


async def test_sun_elevation_threshold_number_async_set_native_value_preserves_other_options(
    mock_hass_with_spec, mock_config_entry_basic
) -> None:
    """Test that async_set_native_value preserves other configuration options.

    Verifies that when updating the sun elevation threshold, all other
    configuration options remain unchanged.
    """
    # Set multiple options in config entry
    mock_config_entry_basic.options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] = 10.0
    mock_config_entry_basic.options[ConfKeys.ENABLED.value] = True
    mock_config_entry_basic.options[ConfKeys.SIMULATION_MODE.value] = False
    mock_config_entry_basic.options["some_other_key"] = "some_value"

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    sun_elevation_threshold_number = SunElevationThresholdNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = AsyncMock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new sun elevation threshold value
    new_value = 45.0
    await sun_elevation_threshold_number.async_set_native_value(new_value)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify the options were updated correctly
    updated_options = mock_update.call_args[1]["options"]
    assert updated_options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == new_value
    assert updated_options[ConfKeys.ENABLED.value] is True
    assert updated_options[ConfKeys.SIMULATION_MODE.value] is False
    assert updated_options["some_other_key"] == "some_value"


async def test_sun_elevation_threshold_number_availability(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that SunElevationThresholdNumber availability tracks coordinator status.

    Verifies that the number entity's availability is linked to the
    coordinator's last_update_success status.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    sun_elevation_threshold_number = SunElevationThresholdNumber(coordinator)

    # Test when coordinator has successful updates
    coordinator.last_update_success = True
    assert sun_elevation_threshold_number.available is True

    # Test when coordinator has failed updates
    coordinator.last_update_success = False
    assert sun_elevation_threshold_number.available is False


async def test_sun_elevation_threshold_number_translation_key_set(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that SunElevationThresholdNumber has translation_key properly set.

    Verifies that the translation_key is set, which is required for
    Home Assistant to properly localize the entity name.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    sun_elevation_threshold_number = SunElevationThresholdNumber(coordinator)

    # Verify translation_key is set
    assert sun_elevation_threshold_number.entity_description.translation_key == NUMBER_KEY_SUN_ELEVATION_THRESHOLD
    assert sun_elevation_threshold_number.entity_description.translation_key is not None


async def test_sun_elevation_threshold_number_config_key_storage(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that SunElevationThresholdNumber properly stores the config key.

    Verifies that the config key is stored correctly and can be used
    to read and update the configuration.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    sun_elevation_threshold_number = SunElevationThresholdNumber(coordinator)

    # Verify the internal config key is set correctly
    assert sun_elevation_threshold_number._config_key == ConfKeys.SUN_ELEVATION_THRESHOLD.value


async def test_sun_elevation_threshold_number_boundary_values(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test SunElevationThresholdNumber with boundary values.

    Verifies that the number entity correctly handles minimum and maximum
    sun elevation values.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    sun_elevation_threshold_number = SunElevationThresholdNumber(coordinator)

    # Test minimum value
    mock_config_entry_basic.options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] = 0.0
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert sun_elevation_threshold_number.native_value == 0.0

    # Test maximum value
    mock_config_entry_basic.options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] = 90.0
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert sun_elevation_threshold_number.native_value == 90.0

    # Test mid-range value
    mock_config_entry_basic.options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] = 45.0
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert sun_elevation_threshold_number.native_value == 45.0


async def test_sun_elevation_async_persist_option_triggers_update_listener(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that _async_persist_option triggers the update listener.

    Verifies that updating an option through the number entity will
    trigger the smart reload listener in __init__.py, which decides
    whether to do a full reload or just refresh the coordinator.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    sun_elevation_threshold_number = SunElevationThresholdNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = AsyncMock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Call _async_persist_option directly
    await sun_elevation_threshold_number._async_persist_option(ConfKeys.SUN_ELEVATION_THRESHOLD.value, 60.0)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify the entry was passed correctly
    assert mock_update.call_args[0][0] == mock_config_entry_basic

    # Verify the new value is in the options
    updated_options = mock_update.call_args[1]["options"]
    assert updated_options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == 60.0
