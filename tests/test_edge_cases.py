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

from datetime import datetime, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES, Platform
from homeassistant.core import HomeAssistant

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_POS_FULLY_CLOSED,
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
    MOCK_WEATHER_ENTITY_ID,
    TEST_COMFORTABLE_TEMP_1,
    MockConfigEntry,
    assert_service_called,
    create_sun_config,
    create_temperature_config,
)


@pytest.mark.asyncio
async def test_non_int_supported_features_does_not_crash() -> None:
    """Test robustness when cover entity has invalid supported_features attribute.

    Validates that the automation system gracefully handles corrupted or invalid
    cover entity attributes without crashing. In real deployments, entity attributes
    might become corrupted due to device issues, integration bugs, or network problems.

    Test scenario:
    - Cover entity: Has string "invalid" instead of integer bitmask for supported_features
    - Sun conditions: Direct hit scenario that would normally trigger automation
    - Expected behavior: No crash occurs, no service calls made (cover safely ignored)

    This ensures the integration remains stable even when Home Assistant entities
    provide malformed data.
    """
    # Setup mock Home Assistant instance with service tracking
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()

    # Setup weather service mock for temperature data
    async def mock_weather_service(domain, service, service_data, **kwargs):
        """Mock weather forecast service that returns temperature data."""
        if domain == Platform.WEATHER and service == "get_forecasts":
            entity_id = service_data.get("entity_id", "weather.forecast")
            return {
                entity_id: {
                    "forecast": [
                        {
                            "datetime": datetime.now(timezone.utc).isoformat(),
                            "native_temperature": 22.0,  # Comfortable temperature
                            "temp_max": 22.0,
                        }
                    ]
                }
            }
        return {}

    hass.services.async_call = AsyncMock(side_effect=mock_weather_service)

    # Create sun-based automation configuration
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = 0  # facing east
    entry = MockConfigEntry(config)

    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity with corrupted supported_features attribute
    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "open"
    cover_state.attributes = {
        ATTR_CURRENT_POSITION: 100,
        ATTR_SUPPORTED_FEATURES: "invalid",  # String instead of integer bitmask
    }

    # Setup sun entity indicating direct hit conditions
    sun_state = MagicMock()
    sun_state.entity_id = MOCK_SUN_ENTITY_ID
    sun_state.state = "above_horizon"
    sun_state.attributes = {"elevation": 50.0, "azimuth": 0.0}

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = lambda entity_id: {
        MOCK_SUN_ENTITY_ID: sun_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_WEATHER_ENTITY_ID: MagicMock(state=TEST_COMFORTABLE_TEMP_1),
    }.get(entity_id)

    # Execute automation logic
    await coordinator.async_refresh()

    # Verify no cover service calls made due to invalid features (graceful handling)
    # Weather service calls are expected, but cover calls should not happen
    cover_service_calls = [
        call
        for call in hass.services.async_call.call_args_list
        if call[0][0] == Platform.COVER  # First positional arg is domain
    ]
    assert len(cover_service_calls) == 0, f"Expected no cover service calls, but got: {cover_service_calls}"


@pytest.mark.asyncio
async def test_duplicate_covers_in_config_do_not_duplicate_actions() -> None:
    """Test that duplicate cover IDs in configuration don't cause duplicate service calls.

    Validates that the automation system properly deduplicates cover entities when
    the same cover ID appears multiple times in the configuration. This could happen
    due to user configuration errors or programmatic configuration generation bugs.

    Test scenario:
    - Configuration: Same cover ID listed twice in the covers array
    - Temperature: Hot (25°C) triggering cover closing
    - Expected behavior: Exactly one service call made (no duplicates)

    This ensures that configuration mistakes don't result in multiple conflicting
    service calls to the same cover entity, which could cause operational issues.
    """
    # Setup mock Home Assistant instance with service call tracking
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()

    # Setup weather service mock for temperature data
    async def mock_weather_service(domain, service, service_data, **kwargs):
        """Mock weather forecast service that returns temperature data."""
        if domain == Platform.WEATHER and service == "get_forecasts":
            entity_id = service_data.get("entity_id", "weather.forecast")
            return {
                entity_id: {
                    "forecast": [
                        {
                            "datetime": datetime.now(timezone.utc).isoformat(),
                            "native_temperature": 25.0,  # Hot temperature triggering closure
                            "temp_max": 25.0,
                        }
                    ]
                }
            }
        return {}

    hass.services.async_call = AsyncMock(side_effect=mock_weather_service)

    # Create temperature automation with duplicate cover IDs
    config = create_temperature_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID])
    entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity that supports position control
    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "open"
    cover_state.attributes = {
        ATTR_CURRENT_POSITION: 100,
        ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
    }

    # Setup temperature sensor indicating hot conditions
    temp_state = MagicMock()
    temp_state.entity_id = MOCK_WEATHER_ENTITY_ID
    temp_state.state = "30.0"  # Hot -> should close

    temp_state.state = "25.0"  # Hot temperature triggering closure in combined logic

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = lambda entity_id: {
        MOCK_WEATHER_ENTITY_ID: temp_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_SUN_ENTITY_ID: MagicMock(state="above_horizon", attributes={"elevation": 30.0, "azimuth": 180.0}),
    }.get(entity_id)

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
    assert len(cover_service_calls) == 1, f"Expected exactly 1 cover service call, but got {len(cover_service_calls)}"


@pytest.mark.asyncio
async def test_boundary_angle_equals_tolerance_is_not_hitting() -> None:
    """Test boundary condition where sun angle difference exactly equals tolerance threshold.

    Validates that the sun angle calculation correctly handles boundary conditions
    where the angle difference between sun azimuth and window orientation exactly
    equals the tolerance threshold (90°). The automation should treat this as
    "not hitting" since the logic uses strict less-than comparison.

    Test scenario:
    - Window orientation: 0° (facing north)
    - Sun azimuth: 90° (due east)
    - Angle difference: 90° (exactly equals tolerance threshold)
    - Expected behavior: Sun not considered hitting, covers should open

    This ensures boundary conditions are handled consistently and predictably.
    """
    # Setup mock Home Assistant instance
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()

    # Setup weather service mock for temperature data
    async def mock_weather_service(domain, service, service_data, **kwargs):
        """Mock weather forecast service that returns temperature data."""
        if domain == Platform.WEATHER and service == "get_forecasts":
            entity_id = service_data.get("entity_id", "weather.forecast")
            return {
                entity_id: {
                    "forecast": [
                        {
                            "datetime": datetime.now(timezone.utc).isoformat(),
                            "native_temperature": 22.0,  # Comfortable temperature
                            "temp_max": 22.0,
                        }
                    ]
                }
            }
        return {}

    hass.services.async_call = AsyncMock(side_effect=mock_weather_service)

    # Create sun automation with window facing north
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    config[f"{MOCK_COVER_ENTITY_ID}_cover_azimuth"] = 0  # North-facing window
    entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity in closed position
    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "closed"
    cover_state.attributes = {
        ATTR_CURRENT_POSITION: 0,
        ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
    }

    # Setup sun at exact tolerance boundary (90° from window)
    sun_state = MagicMock()
    sun_state.entity_id = MOCK_SUN_ENTITY_ID
    sun_state.state = "above_horizon"
    sun_state.attributes = {"elevation": 50.0, "azimuth": 90.0}  # Due east, 90° from north

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = lambda entity_id: {
        MOCK_SUN_ENTITY_ID: sun_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_WEATHER_ENTITY_ID: MagicMock(state=TEST_COMFORTABLE_TEMP_1),
    }.get(entity_id)

    # Execute automation logic
    await coordinator.async_refresh()

    # Verify covers open fully (sun not considered hitting at exact tolerance)
    await assert_service_called(hass.services, "cover", "set_cover_position", MOCK_COVER_ENTITY_ID, position=COVER_POS_FULLY_OPEN)


@pytest.mark.asyncio
async def test_missing_current_position_behaves_safely() -> None:
    """Test robustness when cover entity is missing current_position attribute.

    Validates that the automation system gracefully handles missing position
    information from cover entities. This can occur when covers are offline,
    during Home Assistant startup, or due to device communication issues.

    Test scenario:
    - Cover entity: Missing current_position attribute entirely
    - Temperature: Cold (5°C) indicating covers should open
    - Expected behavior: No crash, defaults to assuming position 100 (open)

    Since the desired position (100) matches the assumed current position (100),
    no service call should be made. This ensures safe operation when position
    data is unavailable.
    """
    # Setup mock Home Assistant instance
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()

    # Setup weather service mock for temperature data
    async def mock_weather_service(domain, service, service_data, **kwargs):
        """Mock weather forecast service that returns temperature data."""
        if domain == Platform.WEATHER and service == "get_forecasts":
            entity_id = service_data.get("entity_id", "weather.forecast")
            return {
                entity_id: {
                    "forecast": [
                        {
                            "datetime": datetime.now(timezone.utc).isoformat(),
                            "native_temperature": 5.0,  # Cold temperature should trigger opening
                            "temp_max": 5.0,
                        }
                    ]
                }
            }
        return {}

    hass.services.async_call = AsyncMock(side_effect=mock_weather_service)

    # Create temperature automation configuration
    config = create_temperature_config(covers=[MOCK_COVER_ENTITY_ID], temp_threshold=24.0)
    entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity WITHOUT current_position attribute
    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "open"
    cover_state.attributes = {
        # Intentionally omit ATTR_CURRENT_POSITION to test missing position handling
        ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
    }

    # Setup temperature sensor indicating cold conditions
    temp_state = MagicMock()
    temp_state.entity_id = MOCK_WEATHER_ENTITY_ID
    temp_state.state = "5.0"  # Cold temperature should trigger opening

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = lambda entity_id: {
        MOCK_WEATHER_ENTITY_ID: temp_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_SUN_ENTITY_ID: MagicMock(state="above_horizon", attributes={"elevation": 30.0, "azimuth": 180.0}),
    }.get(entity_id)

    # Execute automation logic
    await coordinator.async_refresh()

    # Verify no cover service call (desired=100 matches assumed current=100 when missing)
    # Weather service calls are expected, but cover calls should not happen
    cover_service_calls = [
        call
        for call in hass.services.async_call.call_args_list
        if call[0][0] == Platform.COVER  # First positional arg is domain
    ]
    assert len(cover_service_calls) == 0, f"Expected no cover service calls, but got: {cover_service_calls}"


@pytest.mark.asyncio
async def test_invalid_direction_string_skips_cover_in_sun_only() -> None:
    """Test that invalid window direction configuration safely skips cover automation.

    Validates that the automation system gracefully handles invalid window direction
    values in the configuration. When a cover's azimuth direction is configured with
    a non-numeric string value, the cover should be skipped entirely rather than
    causing errors or unexpected behavior.

    Test scenario:
    - Cover azimuth: "south" (invalid string instead of numeric degrees)
    - Sun conditions: Direct hit scenario that would normally trigger automation
    - Temperature: Comfortable (22°C) - no temperature-based action
    - Expected behavior: Cover skipped entirely, no service calls made

    This ensures configuration validation prevents problematic setups from causing
    operational issues while allowing the rest of the system to function normally.
    """
    # Setup mock Home Assistant instance
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()

    # Setup weather service mock for temperature data
    async def mock_weather_service(domain, service, service_data, **kwargs):
        """Mock weather forecast service that returns temperature data."""
        if domain == Platform.WEATHER and service == "get_forecasts":
            entity_id = service_data.get("entity_id", "weather.forecast")
            return {
                entity_id: {
                    "forecast": [
                        {
                            "datetime": datetime.now(timezone.utc).isoformat(),
                            "native_temperature": 22.0,  # Comfortable temperature
                            "temp_max": 22.0,
                        }
                    ]
                }
            }
        return {}

    hass.services.async_call = AsyncMock(side_effect=mock_weather_service)

    # Create combined sun/temperature automation with invalid direction
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    config[ConfKeys.TEMP_THRESHOLD.value] = 24.0  # Add temperature automation
    config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = "south"  # Invalid string value
    entry = MockConfigEntry(config)

    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    # Setup cover entity with partial opening
    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "open"
    cover_state.attributes = {
        ATTR_CURRENT_POSITION: 50,
        ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
    }

    # Setup sun entity indicating direct hit conditions
    sun_state = MagicMock()
    sun_state.entity_id = MOCK_SUN_ENTITY_ID
    sun_state.state = "above_horizon"
    sun_state.attributes = {"elevation": 50.0, "azimuth": 180.0}

    # Configure Home Assistant state lookup
    hass.states.get.side_effect = lambda entity_id: {
        MOCK_SUN_ENTITY_ID: sun_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_WEATHER_ENTITY_ID: MagicMock(state=TEST_COMFORTABLE_TEMP_1),  # Comfortable temperature
    }.get(entity_id)

    # Execute automation logic
    await coordinator.async_refresh()
    result = coordinator.data

    # Verify cover is completely skipped due to invalid direction configuration
    assert result is not None, "Coordinator should return data even with invalid cover configuration"
    assert MOCK_COVER_ENTITY_ID not in result[ConfKeys.COVERS.value]

    # Verify no cover service calls made (cover skipped, comfortable temperature)
    # Weather service calls are expected, but cover calls should not happen
    cover_service_calls = [
        call
        for call in hass.services.async_call.call_args_list
        if call[0][0] == Platform.COVER  # First positional arg is domain
    ]
    assert len(cover_service_calls) == 0, f"Expected no cover service calls, but got: {cover_service_calls}"
