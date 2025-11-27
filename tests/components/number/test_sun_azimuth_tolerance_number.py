"""Tests for SunAzimuthToleranceNumber entity.

This module contains tests for the SunAzimuthToleranceNumber entity, which provides
a UI control for users to adjust the sun azimuth tolerance.

Coverage target: number.py SunAzimuthToleranceNumber class
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast
from unittest.mock import Mock

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import DOMAIN, NUMBER_KEY_SUN_AZIMUTH_TOLERANCE
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.number import SunAzimuthToleranceNumber, async_setup_entry

if TYPE_CHECKING:
    pass


async def test_sun_azimuth_tolerance_number_entity_properties(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test SunAzimuthToleranceNumber entity properties.

    Verifies that the SunAzimuthToleranceNumber entity is properly initialized with:
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

    # Get the sun azimuth tolerance number entity (fourth in list now)
    sun_azimuth_tolerance_number = captured[3]
    assert isinstance(sun_azimuth_tolerance_number, SunAzimuthToleranceNumber)

    # Verify entity description properties
    assert sun_azimuth_tolerance_number.entity_description.key == NUMBER_KEY_SUN_AZIMUTH_TOLERANCE
    assert sun_azimuth_tolerance_number.entity_description.translation_key == NUMBER_KEY_SUN_AZIMUTH_TOLERANCE
    assert sun_azimuth_tolerance_number.entity_description.icon == "mdi:angle-acute"
    assert sun_azimuth_tolerance_number.entity_description.entity_category == EntityCategory.CONFIG

    # Verify unique_id format
    assert sun_azimuth_tolerance_number.unique_id == f"{DOMAIN}_{NUMBER_KEY_SUN_AZIMUTH_TOLERANCE}"

    # Verify numeric properties
    assert sun_azimuth_tolerance_number.entity_description.native_min_value == 0
    assert sun_azimuth_tolerance_number.entity_description.native_max_value == 180
    assert sun_azimuth_tolerance_number.entity_description.native_step == 1
    assert sun_azimuth_tolerance_number.entity_description.mode == NumberMode.BOX
    assert sun_azimuth_tolerance_number.entity_description.native_unit_of_measurement == "°"


async def test_sun_azimuth_tolerance_number_native_value_returns_config_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that native_value property returns the configured sun azimuth tolerance.

    Verifies that the number entity correctly reads the current sun azimuth
    tolerance from the resolved configuration.
    """
    # Set sun azimuth tolerance in config entry options
    mock_config_entry_basic.options[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] = 45

    # Create coordinator with specific sun azimuth tolerance
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    sun_azimuth_tolerance_number = SunAzimuthToleranceNumber(coordinator)

    # Verify that native_value returns the configured sun azimuth tolerance
    assert sun_azimuth_tolerance_number.native_value == 45.0


async def test_sun_azimuth_tolerance_number_native_value_with_different_values(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test native_value with various sun azimuth tolerance values."""
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    sun_azimuth_tolerance_number = SunAzimuthToleranceNumber(coordinator)

    # Test various sun azimuth values
    test_values = [0, 30, 60, 90, 120, 180]

    for value in test_values:
        mock_config_entry_basic.options[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] = value
        # Force re-resolution of config
        coordinator._merged_config = dict(mock_config_entry_basic.options)
        assert sun_azimuth_tolerance_number.native_value == float(value)


async def test_sun_azimuth_tolerance_number_async_set_native_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that async_set_native_value updates the sun azimuth tolerance.

    Verifies that setting a new value through the number entity updates
    the configuration and triggers the appropriate update flow.
    """
    # Set initial sun azimuth tolerance
    mock_config_entry_basic.options[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] = 90

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    sun_azimuth_tolerance_number = SunAzimuthToleranceNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new sun azimuth tolerance value
    new_value = 90.0
    await sun_azimuth_tolerance_number.async_set_native_value(new_value)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify it was called with the correct entry
    call_args = mock_update.call_args
    assert call_args[0][0] == mock_config_entry_basic

    # Verify the options were updated correctly
    updated_options = call_args[1]["options"]
    assert updated_options[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] == new_value


async def test_sun_azimuth_tolerance_number_async_set_native_value_preserves_other_options(
    mock_hass_with_spec, mock_config_entry_basic
) -> None:
    """Test that async_set_native_value preserves other configuration options.

    Verifies that when updating the sun azimuth tolerance, all other
    configuration options remain unchanged.
    """
    # Set multiple options in config entry
    mock_config_entry_basic.options[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] = 90
    mock_config_entry_basic.options[ConfKeys.ENABLED.value] = True
    mock_config_entry_basic.options[ConfKeys.SIMULATION_MODE.value] = False
    mock_config_entry_basic.options["some_other_key"] = "some_value"

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    sun_azimuth_tolerance_number = SunAzimuthToleranceNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new sun azimuth tolerance value
    new_value = 120.0
    await sun_azimuth_tolerance_number.async_set_native_value(new_value)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify the options were updated correctly
    updated_options = mock_update.call_args[1]["options"]
    assert updated_options[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] == new_value
    assert updated_options[ConfKeys.ENABLED.value] is True
    assert updated_options[ConfKeys.SIMULATION_MODE.value] is False
    assert updated_options["some_other_key"] == "some_value"


async def test_sun_azimuth_tolerance_number_availability(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that SunAzimuthToleranceNumber availability tracks coordinator status.

    Verifies that the number entity's availability is linked to the
    coordinator's last_update_success status.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    sun_azimuth_tolerance_number = SunAzimuthToleranceNumber(coordinator)

    # Test when coordinator reports success
    coordinator.last_update_success = True
    assert sun_azimuth_tolerance_number.available is True

    # Test when coordinator reports failure
    coordinator.last_update_success = False
    assert sun_azimuth_tolerance_number.available is False


async def test_sun_azimuth_tolerance_number_coordinator_property(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that SunAzimuthToleranceNumber has proper coordinator reference.

    Verifies that the number entity maintains a reference to its coordinator,
    which is essential for accessing configuration and triggering updates.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    sun_azimuth_tolerance_number = SunAzimuthToleranceNumber(coordinator)

    # Verify coordinator property
    assert sun_azimuth_tolerance_number.coordinator is coordinator


async def test_sun_azimuth_tolerance_number_device_info_links_to_integration(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that SunAzimuthToleranceNumber is properly linked to the integration device.

    Verifies that the number entity appears under the correct device in
    the Home Assistant UI, enabling proper organization and management.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    sun_azimuth_tolerance_number = SunAzimuthToleranceNumber(coordinator)

    # Verify device_info is properly configured
    device_info = sun_azimuth_tolerance_number.device_info
    assert device_info is not None
    assert ("identifiers" in device_info) or ("name" in device_info)


async def test_sun_azimuth_tolerance_number_boundary_values(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test SunAzimuthToleranceNumber with boundary values.

    Verifies that the number entity correctly handles minimum and maximum
    values according to its specification (0-180 degrees).
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    sun_azimuth_tolerance_number = SunAzimuthToleranceNumber(coordinator)

    # Test minimum boundary value
    mock_config_entry_basic.options[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] = 0
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert sun_azimuth_tolerance_number.native_value == 0.0

    # Test maximum boundary value
    mock_config_entry_basic.options[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] = 180
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert sun_azimuth_tolerance_number.native_value == 180.0


async def test_sun_azimuth_tolerance_number_default_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test SunAzimuthToleranceNumber with default configuration.

    Verifies that when no explicit value is configured, the number entity
    uses the default value from the configuration specification (90 degrees).
    """
    # Don't set any explicit value in config entry options
    # Should use default from config specs

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    sun_azimuth_tolerance_number = SunAzimuthToleranceNumber(coordinator)

    # Verify that native_value returns the default sun azimuth tolerance (90 degrees)
    assert sun_azimuth_tolerance_number.native_value == 90.0
