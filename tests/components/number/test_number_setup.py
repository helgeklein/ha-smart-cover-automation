"""Tests for number platform setup.

This module tests the async_setup_entry function that creates and registers
all number entities when the integration is loaded.

Coverage target: number.py lines 31-54 (async_setup_entry function)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES

from custom_components.smart_cover_automation.number import (
    CoverExternalTiltDayNumber,
    CoverExternalTiltNightNumber,
    CoversMaxClosureNumber,
    CoversMinClosureNumber,
    DailyMaxTemperatureThresholdNumber,
    DailyMinTemperatureThresholdNumber,
    GlobalExternalTiltDayNumber,
    GlobalExternalTiltNightNumber,
    ManualOverrideDurationNumber,
    SunAzimuthToleranceNumber,
    SunElevationThresholdNumber,
    async_setup_entry,
)
from tests.conftest import set_test_options

if TYPE_CHECKING:
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


async def test_async_setup_entry_creates_all_numbers(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test that async_setup_entry creates all number entities.

    Verifies that the setup function creates instances of:
    - DailyMaxTemperatureThresholdNumber
    - DailyMinTemperatureThresholdNumber

    Coverage target: number.py lines 31-54
    """
    # Create mock config entry with runtime data
    mock_entry = MagicMock()
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.coordinator = mock_coordinator_basic

    # Create mock async_add_entities callback
    mock_add_entities = MagicMock()

    # Call async_setup_entry
    await async_setup_entry(
        hass=MagicMock(),  # hass is unused but required by interface
        entry=mock_entry,
        async_add_entities=mock_add_entities,
    )

    # Verify async_add_entities was called
    mock_add_entities.assert_called_once()

    # Get the list of entities that were passed to async_add_entities
    entities_list = mock_add_entities.call_args[0][0]

    # Verify we have exactly 7 entities
    assert len(entities_list) == 7

    # Verify entity types (alphabetically ordered)
    assert isinstance(entities_list[0], CoversMaxClosureNumber)
    assert isinstance(entities_list[1], CoversMinClosureNumber)
    assert isinstance(entities_list[2], ManualOverrideDurationNumber)
    assert isinstance(entities_list[3], SunAzimuthToleranceNumber)
    assert isinstance(entities_list[4], SunElevationThresholdNumber)
    assert isinstance(entities_list[5], DailyMaxTemperatureThresholdNumber)
    assert isinstance(entities_list[6], DailyMinTemperatureThresholdNumber)


async def test_async_setup_entry_entities_use_coordinator(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test that all created numbers are properly linked to the coordinator.

    Verifies that each number entity receives and stores a reference to
    the coordinator, enabling them to read configuration and trigger updates.

    Coverage target: number.py lines 31-54
    """
    # Create mock config entry with runtime data
    mock_entry = MagicMock()
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.coordinator = mock_coordinator_basic

    # Create mock async_add_entities callback
    mock_add_entities = MagicMock()

    # Call async_setup_entry
    await async_setup_entry(
        hass=MagicMock(),
        entry=mock_entry,
        async_add_entities=mock_add_entities,
    )

    # Get the list of entities
    entities_list = mock_add_entities.call_args[0][0]

    # Verify all entities have the coordinator
    for entity in entities_list:
        assert entity.coordinator is mock_coordinator_basic


async def test_async_setup_entry_with_real_hass_instance(
    mock_hass_with_spec,
    mock_config_entry_basic,
) -> None:
    """Test async_setup_entry with a real-ish Home Assistant instance.

    This test uses a more realistic mock of Home Assistant to verify that
    the setup process works correctly with actual HA components.

    Coverage target: number.py lines 31-54
    """
    from typing import Iterable, cast

    from homeassistant.helpers.entity import Entity

    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
    from custom_components.smart_cover_automation.data import IntegrationConfigEntry

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

    # Should have 7 number entities
    assert len(captured) == 7
    assert isinstance(captured[0], CoversMaxClosureNumber)
    assert isinstance(captured[1], CoversMinClosureNumber)
    assert isinstance(captured[2], ManualOverrideDurationNumber)
    assert isinstance(captured[3], SunAzimuthToleranceNumber)
    assert isinstance(captured[4], SunElevationThresholdNumber)
    assert isinstance(captured[5], DailyMaxTemperatureThresholdNumber)
    assert isinstance(captured[6], DailyMinTemperatureThresholdNumber)


async def test_async_setup_entry_adds_external_tilt_numbers_when_modes_external(mock_coordinator_basic: DataUpdateCoordinator) -> None:
    """Test that dynamic external tilt number entities are added when configured."""

    entry = mock_coordinator_basic.config_entry
    set_test_options(
        entry,
        {
            **dict(entry.options),
            "tilt_mode_day": "external",
            "tilt_mode_night": "external",
            "cover.test_cover_cover_tilt_mode_day": "external",
            "cover.test_cover_cover_tilt_mode_night": "external",
        },
    )
    entry.runtime_data.coordinator = mock_coordinator_basic
    mock_coordinator_basic.hass.states.get.return_value = MagicMock(
        attributes={ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION}
    )

    captured = []

    def add_entities(new_entities, update_before_add: bool = False) -> None:  # noqa: ARG001, ANN001
        captured.extend(list(new_entities))

    await async_setup_entry(mock_coordinator_basic.hass, entry, add_entities)

    assert len(captured) == 11
    assert isinstance(captured[7], GlobalExternalTiltDayNumber)
    assert isinstance(captured[8], GlobalExternalTiltNightNumber)
    assert isinstance(captured[9], CoverExternalTiltDayNumber)
    assert isinstance(captured[10], CoverExternalTiltNightNumber)


async def test_async_setup_entry_skips_per_cover_external_tilt_numbers_without_tilt_support(
    mock_coordinator_basic: DataUpdateCoordinator,
) -> None:
    """Per-cover external tilt numbers should not be created for non-tilt-capable covers."""

    entry = mock_coordinator_basic.config_entry
    set_test_options(
        entry,
        {
            **dict(entry.options),
            "tilt_mode_day": "external",
            "tilt_mode_night": "external",
            "cover.test_cover_cover_tilt_mode_day": "external",
            "cover.test_cover_cover_tilt_mode_night": "external",
        },
    )
    entry.runtime_data.coordinator = mock_coordinator_basic

    mock_coordinator_basic.hass.states.get.return_value = MagicMock(attributes={ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION})

    captured = []

    def add_entities(new_entities, update_before_add: bool = False) -> None:  # noqa: ARG001, ANN001
        captured.extend(list(new_entities))

    await async_setup_entry(mock_coordinator_basic.hass, entry, add_entities)

    assert len(captured) == 9
    assert isinstance(captured[7], GlobalExternalTiltDayNumber)
    assert isinstance(captured[8], GlobalExternalTiltNightNumber)
    assert not any(isinstance(entity, CoverExternalTiltDayNumber) for entity in captured)
    assert not any(isinstance(entity, CoverExternalTiltNightNumber) for entity in captured)
