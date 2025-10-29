"""Edge-case tests for Smart Cover Automation robustness.

This module contains tests for unusual, boundary, and error conditions that might
occur in real-world deployments. These tests ensure the automation system remains
stable and behaves predictably when encountering:

- Invalid or malformed configuration data
- Corrupted sensor readings or entity attributes
- Boundary conditions and edge values
- Duplicate or conflicting configuration entries
- Missing or incomplete entity state information

The tests focus on robustness rather than normal operation, verifying that:
- No crashes occur with invalid inputs
- Service calls are handled safely and appropriately
- Error conditions are gracefully managed
- Edge cases don't cause unexpected automation behavior
- Configuration validation catches problematic setups

These edge case tests complement the main test suites by ensuring the integration
can handle real-world deployment scenarios where data may be inconsistent or
configuration mistakes might occur.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES, Platform

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_ATTR_COVER_AZIMUTH,
    COVER_POS_FULLY_CLOSED,
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
    HA_WEATHER_COND_SUNNY,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from ..conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
    MOCK_WEATHER_ENTITY_ID,
    TEST_COMFORTABLE_TEMP_1,
    MockConfigEntry,
    assert_service_called,
    create_mock_hass_with_weather_service,
    create_mock_state_getter,
    create_standard_cover_state,
    create_standard_sun_state,
    create_sun_config,
    create_temperature_config,
    set_weather_forecast_temp,
)


@pytest.mark.parametrize(
    "invalid_features,description",
    [
        ("invalid", "string instead of integer"),
        (None, "None value"),
        ([], "empty list"),
        ({}, "empty dict"),
        (3.14, "float value"),
        ("15.5", "numeric string"),
    ],
)
async def test_non_int_supported_features_does_not_crash(invalid_features: Any, description: str) -> None:
    """Test robustness when cover entity has invalid supported_features attribute.

    Validates that the automation system gracefully handles corrupted or invalid
    cover entity attributes without crashing. In real deployments, entity attributes
    might become corrupted due to device issues, integration bugs, or network problems.

    Test scenario:
    - Cover entity: Has invalid value instead of integer bitmask for supported_features
    - Sun conditions: Direct hit scenario that would normally trigger automation
    - Expected behavior: No crash occurs, no service calls made (cover safely ignored)

    This ensures the integration remains stable even when Home Assistant entities
    provide malformed data.
    """
    # Setup mock Home Assistant instance with weather service
    hass = create_mock_hass_with_weather_service()
    set_weather_forecast_temp(22.0)  # Comfortable temperature

    # Create sun-based automation configuration
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = 0  # facing east
    entry = MockConfigEntry(config)

    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity with corrupted supported_features attribute
    cover_state = create_standard_cover_state()
    cover_state.state = "open"
    cover_state.attributes[ATTR_SUPPORTED_FEATURES] = invalid_features  # Invalid value type

    # Setup sun entity indicating direct hit conditions
    sun_state = create_standard_sun_state(elevation=50.0, azimuth=0.0)

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = create_mock_state_getter(
        **{
            MOCK_SUN_ENTITY_ID: sun_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_WEATHER_ENTITY_ID: MagicMock(state=TEST_COMFORTABLE_TEMP_1),
        }
    )

    # Execute automation logic
    await coordinator.async_refresh()

    # Verify no cover service calls made due to invalid features (graceful handling)
    # Weather service calls are expected, but cover calls should not happen
    cover_service_calls = [
        call
        for call in hass.services.async_call.call_args_list
        if call[0][0] == Platform.COVER  # First positional arg is domain
    ]
    assert len(cover_service_calls) == 0, f"Expected no cover service calls with {description}, but got: {cover_service_calls}"


@pytest.mark.parametrize(
    "covers_list,expected_calls,description",
    [
        ([MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID], 1, "duplicate covers"),
        ([MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID], 1, "triple duplicate covers"),
        ([MOCK_COVER_ENTITY_ID], 1, "single cover (baseline)"),
    ],
)
async def test_duplicate_covers_in_config_do_not_duplicate_actions(covers_list: list[str], expected_calls: int, description: str) -> None:
    """Test that duplicate cover IDs in configuration don't cause duplicate service calls.

    Validates that the automation system properly deduplicates cover entities when
    the same cover ID appears multiple times in the configuration. This could happen
    due to user configuration errors or programmatic configuration generation bugs.

    Test scenario:
    - Configuration: Same cover ID listed multiple times in the covers array
    - Temperature: Hot (25°C) triggering cover closing
    - Expected behavior: Exactly one service call made (no duplicates)

    This ensures that configuration mistakes don't result in multiple conflicting
    service calls to the same cover entity, which could cause operational issues.
    """
    # Setup mock Home Assistant instance with weather service
    hass = create_mock_hass_with_weather_service()
    set_weather_forecast_temp(25.0)  # Hot temperature triggering closure

    # Create temperature automation with duplicate cover IDs
    config = create_temperature_config(covers=covers_list)
    entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity that supports position control
    cover_state = create_standard_cover_state()
    cover_state.state = "open"
    cover_state.attributes[ATTR_SUPPORTED_FEATURES] = CoverEntityFeature.SET_POSITION

    # Setup weather entity indicating sunny conditions (for weather condition check)
    weather_state = MagicMock()
    weather_state.entity_id = MOCK_WEATHER_ENTITY_ID
    weather_state.state = HA_WEATHER_COND_SUNNY  # Sunny weather condition for automation to work

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = create_mock_state_getter(
        **{
            MOCK_WEATHER_ENTITY_ID: weather_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: MagicMock(state="above_horizon", attributes={"elevation": 30.0, "azimuth": 180.0}),
        }
    )

    # Execute automation logic
    await coordinator.async_refresh()

    # Verify exactly one cover service call (duplicates are deduplicated by state dict keys)
    await assert_service_called(hass.services, "cover", "set_cover_position", MOCK_COVER_ENTITY_ID, position=COVER_POS_FULLY_CLOSED)

    # Count only cover service calls (weather calls are expected but don't count for duplication test)
    cover_service_calls = [
        call
        for call in hass.services.async_call.call_args_list
        if call[0][0] == Platform.COVER  # First positional arg is domain
    ]
    assert len(cover_service_calls) == expected_calls, (
        f"Expected exactly {expected_calls} cover service call with {description}, but got {len(cover_service_calls)}"
    )


@pytest.mark.parametrize(
    "window_azimuth,sun_azimuth,expected_position,description",
    [
        (0, 90, COVER_POS_FULLY_OPEN, "north window, east sun (90° difference - boundary)"),
        (180, 270, COVER_POS_FULLY_OPEN, "south window, west sun (90° difference - boundary)"),
        (90, 180, COVER_POS_FULLY_OPEN, "east window, south sun (90° difference - boundary)"),
        (270, 0, COVER_POS_FULLY_OPEN, "west window, north sun (90° difference - boundary)"),
        (0, 89, COVER_POS_FULLY_OPEN, "north window, east sun (89° difference - within tolerance)"),
        (180, 269, COVER_POS_FULLY_OPEN, "south window, west sun (89° difference - within tolerance)"),
    ],
)
async def test_boundary_angle_equals_tolerance_is_not_hitting(
    window_azimuth: float, sun_azimuth: float, expected_position: int, description: str
) -> None:
    """Test boundary condition where sun angle difference equals or near tolerance threshold.

    Validates that the sun angle calculation correctly handles boundary conditions
    where the angle difference between sun azimuth and window orientation exactly
    equals or is near the tolerance threshold (90°). The automation should treat
    exactly 90° as "not hitting" since the logic uses strict less-than comparison.

    Test scenario:
    - Window orientation: Various directions
    - Sun azimuth: Various positions relative to window
    - Angle difference: At or near 90° tolerance threshold
    - Expected behavior: Consistent boundary handling

    This ensures boundary conditions are handled consistently and predictably.
    """
    # Setup mock Home Assistant instance with weather service
    hass = create_mock_hass_with_weather_service()
    set_weather_forecast_temp(22.0)  # Comfortable temperature

    # Create sun automation with specified window orientation
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    config[f"{MOCK_COVER_ENTITY_ID}_cover_azimuth"] = window_azimuth
    entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity in closed position
    cover_state = create_standard_cover_state(position=0)
    cover_state.state = "closed"
    cover_state.attributes[ATTR_SUPPORTED_FEATURES] = CoverEntityFeature.SET_POSITION

    # Setup sun at specified azimuth position
    sun_state = create_standard_sun_state(elevation=50.0, azimuth=sun_azimuth)

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = create_mock_state_getter(
        **{
            MOCK_SUN_ENTITY_ID: sun_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_WEATHER_ENTITY_ID: MagicMock(state=TEST_COMFORTABLE_TEMP_1),
        }
    )

    # Execute automation logic
    await coordinator.async_refresh()

    # Verify expected cover position based on angle calculation
    await assert_service_called(hass.services, "cover", "set_cover_position", MOCK_COVER_ENTITY_ID, position=expected_position)


@pytest.mark.parametrize(
    "position_value,temp_condition,expected_calls",
    [
        (None, 30.0, 1),  # missing position attribute when hot - still processes
        ("unavailable", 30.0, 1),  # unavailable position when hot - still processes (with error handling)
        ("unknown", 15.0, 1),  # unknown position when cold - still processes (with error handling)
        (None, 15.0, 1),  # missing position when cold - still processes
    ],
)
async def test_missing_current_position_behaves_safely(position_value: Any, temp_condition: float, expected_calls: int) -> None:
    """Test automation behavior when cover position is missing or invalid.

    Validates handling of edge cases where the cover's current position
    is missing, unavailable, or in an unknown state. The automation still
    attempts to process these covers but may encounter errors during execution.

    Test scenarios:
    - Position attribute missing/invalid in various temperature conditions
    - Expected behavior: Automation attempts processing but may fail gracefully

    This ensures the system attempts to work with problematic devices
    while handling any errors that occur during processing.
    """
    # Setup mock Home Assistant instance
    hass = create_mock_hass_with_weather_service()
    set_weather_forecast_temp(temp_condition)

    # Create automation configuration
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover with problematic position value
    cover_state = create_standard_cover_state(position=0)
    if position_value is None:
        # Remove position attribute entirely
        del cover_state.attributes[ATTR_CURRENT_POSITION]
    else:
        cover_state.attributes[ATTR_CURRENT_POSITION] = position_value

    # Setup appropriate weather and sun conditions
    hass.states.get.side_effect = create_mock_state_getter(
        **{
            MOCK_SUN_ENTITY_ID: create_standard_sun_state(elevation=50.0, azimuth=0),
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_WEATHER_ENTITY_ID: MagicMock(state=str(temp_condition)),
        }
    )

    # Execute automation
    await coordinator.async_refresh()

    # Verify expected number of service calls (only count cover service calls, not weather)
    cover_calls = [
        call
        for call in hass.services.async_call.call_args_list
        if call[0][0] == "cover" or (len(call.args) > 0 and call.args[0] == "cover")
    ]
    assert len(cover_calls) == expected_calls


@pytest.mark.parametrize(
    "invalid_direction,expected_error_contains,description",
    [
        ("south", "invalid or missing azimuth", "string direction name"),
        ("", "invalid or missing azimuth", "empty string"),
        (None, "invalid or missing azimuth", "None value"),
        ([], "invalid or missing azimuth", "empty list"),
    ],
)
async def test_invalid_direction_string_skips_cover_in_sun_only(
    invalid_direction: Any, expected_error_contains: str, description: str
) -> None:
    """Test that invalid window direction configuration safely skips cover automation.

    Validates that the automation system gracefully handles invalid window direction
    values in the configuration. When a cover's azimuth direction is configured with
    invalid values, the cover should be marked with an error rather than
    causing crashes or unexpected behavior.

    Test scenario:
    - Cover azimuth: Various invalid values instead of numeric degrees
    - Sun conditions: Direct hit scenario that would normally trigger automation
    - Temperature: Comfortable (22°C) - no temperature-based action
    - Expected behavior: Cover marked with error, no service calls made

    This ensures configuration validation prevents problematic setups from causing
    operational issues while allowing the rest of the system to function normally.
    """
    # Setup mock Home Assistant instance with weather service
    hass = create_mock_hass_with_weather_service()
    set_weather_forecast_temp(22.0)  # Comfortable temperature

    # Create combined sun/temperature automation with invalid direction
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    config[ConfKeys.TEMP_THRESHOLD.value] = 24.0  # Add temperature automation
    config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = invalid_direction  # Invalid value
    entry = MockConfigEntry(config)

    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity with partial opening
    cover_state = create_standard_cover_state(position=50)
    cover_state.state = "open"
    cover_state.attributes[ATTR_SUPPORTED_FEATURES] = CoverEntityFeature.SET_POSITION

    # Setup sun entity indicating direct hit conditions
    sun_state = create_standard_sun_state(elevation=50.0, azimuth=180.0)

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = create_mock_state_getter(
        **{
            MOCK_SUN_ENTITY_ID: sun_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_WEATHER_ENTITY_ID: MagicMock(state=TEST_COMFORTABLE_TEMP_1),  # Comfortable temperature
        }
    )

    # Execute automation logic
    await coordinator.async_refresh()

    # Verify no cover service calls made (cover skipped, comfortable temperature)
    # Weather service calls are expected, but cover calls should not happen
    cover_service_calls = [
        call
        for call in hass.services.async_call.call_args_list
        if call[0][0] == Platform.COVER  # First positional arg is domain
    ]
    assert len(cover_service_calls) == 0, f"Expected no cover service calls with {description}, but got: {cover_service_calls}"


@pytest.mark.parametrize(
    "numeric_direction,expected_processed,description",
    [
        ("360.5", True, "out of range numeric string (accepted as 360.5)"),
        ("-45", True, "negative numeric string (accepted as -45.0)"),
    ],
)
async def test_numeric_direction_strings_are_processed(numeric_direction: str, expected_processed: bool, description: str) -> None:
    """Test that numeric direction strings are accepted and processed.

    Validates that numeric strings, even those outside normal 0-360 range,
    are parsed and processed as valid azimuth values. The system accepts
    these values and processes them through the automation logic.

    Test scenarios:
    - Numeric strings outside normal range: Should be accepted and processed
    - Negative angles: Should be accepted and processed

    This ensures the system is flexible with numeric input formats
    while maintaining functionality.
    """
    # Setup mock Home Assistant instance with weather service
    hass = create_mock_hass_with_weather_service()
    set_weather_forecast_temp(22.0)  # Comfortable temperature

    # Create sun automation configuration with numeric direction string
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = numeric_direction
    entry = MockConfigEntry(config)

    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity with partial opening
    cover_state = create_standard_cover_state(position=50)
    cover_state.state = "open"
    cover_state.attributes[ATTR_SUPPORTED_FEATURES] = CoverEntityFeature.SET_POSITION

    # Setup sun entity indicating direct hit conditions
    sun_state = create_standard_sun_state(elevation=50.0, azimuth=180.0)

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = create_mock_state_getter(
        **{
            MOCK_SUN_ENTITY_ID: sun_state,
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_WEATHER_ENTITY_ID: MagicMock(state=TEST_COMFORTABLE_TEMP_1),  # Comfortable temperature
        }
    )

    # Execute automation logic
    await coordinator.async_refresh()
    result = coordinator.data

    # Verify numeric string was processed successfully
    assert result is not None, f"Coordinator should return data for numeric direction string ({description})"
    assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
    cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]

    if expected_processed:
        # Should have azimuth as float and no error
        assert COVER_ATTR_COVER_AZIMUTH in cover_data, f"Expected azimuth field for {description}"
        assert isinstance(cover_data[COVER_ATTR_COVER_AZIMUTH], float), f"Expected float azimuth for {description}"
