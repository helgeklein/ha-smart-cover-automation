"""Tests for ManualOverrideDurationNumber entity.

This module contains tests for the ManualOverrideDurationNumber entity, which provides
a UI control for users to adjust the manual override duration in minutes.

Coverage target: number.py ManualOverrideDurationNumber class
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast
from unittest.mock import Mock

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.helpers.entity import Entity

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import DOMAIN, NUMBER_KEY_MANUAL_OVERRIDE_DURATION
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.number import ManualOverrideDurationNumber, async_setup_entry

if TYPE_CHECKING:
    pass


async def test_manual_override_duration_number_entity_properties(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test ManualOverrideDurationNumber entity properties.

    Verifies that the ManualOverrideDurationNumber entity is properly initialized with:
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

    # Get the manual override duration number entity (third in list)
    manual_override_duration_number = captured[2]
    assert isinstance(manual_override_duration_number, ManualOverrideDurationNumber)

    # Verify entity description properties
    assert manual_override_duration_number.entity_description.key == NUMBER_KEY_MANUAL_OVERRIDE_DURATION
    assert manual_override_duration_number.entity_description.translation_key == NUMBER_KEY_MANUAL_OVERRIDE_DURATION
    assert manual_override_duration_number.entity_description.icon == "mdi:timer-outline"
    assert manual_override_duration_number.entity_description.entity_category == EntityCategory.CONFIG

    # Verify unique_id format
    assert manual_override_duration_number.unique_id == f"{DOMAIN}_{NUMBER_KEY_MANUAL_OVERRIDE_DURATION}"

    # Verify numeric properties
    assert manual_override_duration_number.entity_description.native_min_value == 0
    assert manual_override_duration_number.entity_description.native_max_value is None  # Unlimited
    assert manual_override_duration_number.entity_description.native_step == 1
    assert manual_override_duration_number.entity_description.mode == NumberMode.BOX
    assert manual_override_duration_number.entity_description.native_unit_of_measurement == UnitOfTime.MINUTES


async def test_manual_override_duration_number_native_value_returns_config_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that native_value property returns the configured duration in minutes.

    Verifies that the number entity correctly reads the current manual override duration
    from the resolved configuration and converts from seconds to minutes.
    """
    # Set manual override duration in config entry options (in seconds)
    mock_config_entry_basic.options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 3600  # 60 minutes

    # Create coordinator with specific duration
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    manual_override_duration_number = ManualOverrideDurationNumber(coordinator)

    # Verify that native_value returns the duration in minutes
    assert manual_override_duration_number.native_value == 60.0


async def test_manual_override_duration_number_native_value_with_different_values(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test native_value with various duration values."""
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    manual_override_duration_number = ManualOverrideDurationNumber(coordinator)

    # Test various duration values (seconds -> minutes)
    test_values = [
        (0, 0.0),  # 0 seconds = 0 minutes
        (60, 1.0),  # 60 seconds = 1 minute
        (300, 5.0),  # 300 seconds = 5 minutes
        (1800, 30.0),  # 1800 seconds = 30 minutes (default)
        (3600, 60.0),  # 3600 seconds = 60 minutes
        (7200, 120.0),  # 7200 seconds = 120 minutes
    ]

    for seconds, expected_minutes in test_values:
        mock_config_entry_basic.options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = seconds
        # Force re-resolution of config
        coordinator._merged_config = dict(mock_config_entry_basic.options)
        assert manual_override_duration_number.native_value == expected_minutes


async def test_manual_override_duration_number_async_set_native_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that async_set_native_value updates the duration and converts to seconds.

    Verifies that setting a new value through the number entity updates
    the configuration and triggers the appropriate update flow.
    """
    # Set initial duration
    mock_config_entry_basic.options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800  # 30 minutes

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    manual_override_duration_number = ManualOverrideDurationNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new duration value in minutes
    new_value = 45.0  # 45 minutes
    await manual_override_duration_number.async_set_native_value(new_value)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify it was called with the correct entry
    call_args = mock_update.call_args
    assert call_args[0][0] == mock_config_entry_basic

    # Verify the options were updated correctly (should be in seconds)
    updated_options = call_args[1]["options"]
    assert updated_options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] == 2700  # 45 * 60


async def test_manual_override_duration_number_async_set_native_value_preserves_other_options(
    mock_hass_with_spec, mock_config_entry_basic
) -> None:
    """Test that async_set_native_value preserves other configuration options.

    Verifies that when updating the manual override duration, all other
    configuration options remain unchanged.
    """
    # Set multiple options in config entry
    mock_config_entry_basic.options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 1800
    mock_config_entry_basic.options[ConfKeys.ENABLED.value] = True
    mock_config_entry_basic.options[ConfKeys.SIMULATION_MODE.value] = False
    mock_config_entry_basic.options["some_other_key"] = "some_value"

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    manual_override_duration_number = ManualOverrideDurationNumber(coordinator)

    # Mock the hass.config_entries.async_update_entry method
    mock_update = Mock()
    coordinator.hass.config_entries.async_update_entry = mock_update

    # Set a new duration value
    new_value = 60.0  # 60 minutes = 3600 seconds
    await manual_override_duration_number.async_set_native_value(new_value)

    # Verify async_update_entry was called
    mock_update.assert_called_once()

    # Verify the options were updated correctly
    updated_options = mock_update.call_args[1]["options"]
    assert updated_options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] == 3600
    assert updated_options[ConfKeys.ENABLED.value] is True
    assert updated_options[ConfKeys.SIMULATION_MODE.value] is False
    assert updated_options["some_other_key"] == "some_value"


async def test_manual_override_duration_number_availability(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that ManualOverrideDurationNumber availability tracks coordinator status.

    Verifies that the number entity's availability is linked to the
    coordinator's last_update_success status.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))

    # Create the number entity
    manual_override_duration_number = ManualOverrideDurationNumber(coordinator)

    # Test when coordinator reports success
    coordinator.last_update_success = True
    assert manual_override_duration_number.available is True

    # Test when coordinator reports failure
    coordinator.last_update_success = False
    assert manual_override_duration_number.available is False


async def test_manual_override_duration_number_coordinator_property(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that ManualOverrideDurationNumber has proper coordinator reference.

    Verifies that the number entity maintains a reference to its coordinator,
    which is essential for accessing configuration and triggering updates.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    manual_override_duration_number = ManualOverrideDurationNumber(coordinator)

    # Verify coordinator property
    assert manual_override_duration_number.coordinator is coordinator


async def test_manual_override_duration_number_device_info_links_to_integration(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test that ManualOverrideDurationNumber is properly linked to the integration device.

    Verifies that the number entity appears under the correct device in
    the Home Assistant UI, enabling proper organization and management.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    manual_override_duration_number = ManualOverrideDurationNumber(coordinator)

    # Verify device_info is properly configured
    device_info = manual_override_duration_number.device_info
    assert device_info is not None
    assert ("identifiers" in device_info) or ("name" in device_info)


async def test_manual_override_duration_number_boundary_values(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test ManualOverrideDurationNumber with boundary values.

    Verifies that the number entity correctly handles minimum value (0)
    and very large values.
    """
    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True
    mock_config_entry_basic.runtime_data.coordinator = coordinator

    # Create the number entity
    manual_override_duration_number = ManualOverrideDurationNumber(coordinator)

    # Test minimum boundary value (0 seconds = 0 minutes)
    mock_config_entry_basic.options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 0
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert manual_override_duration_number.native_value == 0.0

    # Test large value (24 hours = 1440 minutes)
    mock_config_entry_basic.options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] = 86400  # 24 hours in seconds
    coordinator._merged_config = dict(mock_config_entry_basic.options)
    assert manual_override_duration_number.native_value == 1440.0


async def test_manual_override_duration_number_default_value(mock_hass_with_spec, mock_config_entry_basic) -> None:
    """Test ManualOverrideDurationNumber with default configuration.

    Verifies that when no explicit value is configured, the number entity
    uses the default value from the configuration specification (1800 seconds = 30 minutes).
    """
    # Don't set any explicit value in config entry options
    # Should use default from config specs

    # Create coordinator
    coordinator = DataUpdateCoordinator(mock_hass_with_spec, cast(IntegrationConfigEntry, mock_config_entry_basic))
    coordinator.last_update_success = True

    # Create the number entity
    manual_override_duration_number = ManualOverrideDurationNumber(coordinator)

    # Verify that native_value returns the default duration (1800 seconds = 30 minutes)
    assert manual_override_duration_number.native_value == 30.0
