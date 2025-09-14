"""Edge-case tests for Smart Cover Automation.

Covers unlikely or impossible inputs to ensure robustness and no crashes.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.core import HomeAssistant

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import COVER_SFX_AZIMUTH
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    MockConfigEntry,
    assert_service_called,
    create_sun_config,
    create_temperature_config,
)


@pytest.mark.asyncio
async def test_non_int_supported_features_does_not_crash() -> None:
    """If supported_features is a non-int, we should not crash and no service is called."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    # Sun-only config with direct hit, but features attribute is an invalid string
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = 0  # facing east
    entry = MockConfigEntry(config)

    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "open"
    cover_state.attributes = {
        ATTR_CURRENT_POSITION: 100,
        "supported_features": "invalid",  # Not an int/bitmask
    }

    sun_state = MagicMock()
    sun_state.entity_id = MOCK_SUN_ENTITY_ID
    sun_state.state = "above_horizon"
    sun_state.attributes = {"elevation": 50.0, "azimuth": 0.0}

    hass.states.get.side_effect = lambda entity_id: {
        MOCK_SUN_ENTITY_ID: sun_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_TEMP_SENSOR_ENTITY_ID: MagicMock(state="22.0"),
    }.get(entity_id)

    await coordinator.async_refresh()

    # No service should have been called due to invalid features, but no crash
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_covers_in_config_do_not_duplicate_actions() -> None:
    """Duplicate cover IDs should be deduplicated internally and not cause duplicate actions."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    # Temperature-only config with duplicates
    config = create_temperature_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID])
    entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "open"
    cover_state.attributes = {
        ATTR_CURRENT_POSITION: 100,
        "supported_features": CoverEntityFeature.SET_POSITION,
    }

    temp_state = MagicMock()
    temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID
    temp_state.state = "30.0"  # Hot -> should close

    temp_state.state = "25.0"  # Hot temp for AND logic

    hass.states.get.side_effect = lambda entity_id: {
        MOCK_TEMP_SENSOR_ENTITY_ID: temp_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_SUN_ENTITY_ID: MagicMock(state="above_horizon", attributes={"elevation": 30.0, "azimuth": 180.0}),
    }.get(entity_id)

    await coordinator.async_refresh()

    # Because states dict uses keys, duplicates collapse to one
    # Expect exactly one set_cover_position call
    await assert_service_called(hass.services, "cover", "set_cover_position", MOCK_COVER_ENTITY_ID, position=0)
    assert hass.services.async_call.call_count == 1


@pytest.mark.asyncio
async def test_boundary_angle_equals_tolerance_is_not_hitting() -> None:
    """Angle difference equal to tolerance should be treated as not hitting (strict <)."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    # window direction = 0°, sun azimuth = 90° => angle diff = 90 (tolerance)
    config[f"{MOCK_COVER_ENTITY_ID}_cover_azimuth"] = 0
    entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "closed"
    cover_state.attributes = {
        ATTR_CURRENT_POSITION: 0,
        "supported_features": CoverEntityFeature.SET_POSITION,
    }

    sun_state = MagicMock()
    sun_state.entity_id = MOCK_SUN_ENTITY_ID
    sun_state.state = "above_horizon"
    sun_state.attributes = {"elevation": 50.0, "azimuth": 90.0}

    hass.states.get.side_effect = lambda entity_id: {
        MOCK_SUN_ENTITY_ID: sun_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_TEMP_SENSOR_ENTITY_ID: MagicMock(state="22.0"),
    }.get(entity_id)

    await coordinator.async_refresh()

    # Should open fully (not hitting)
    await assert_service_called(hass.services, "cover", "set_cover_position", MOCK_COVER_ENTITY_ID, position=100)


@pytest.mark.asyncio
async def test_missing_current_position_behaves_safely() -> None:
    """If current_position is missing, coordinator should still behave safely (no crash) and pick a sane action."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    config = create_temperature_config(covers=[MOCK_COVER_ENTITY_ID], temp_threshold=24.0)
    entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "open"
    cover_state.attributes = {
        # intentionally omit current_position
        "supported_features": CoverEntityFeature.SET_POSITION,
    }

    temp_state = MagicMock()
    temp_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID
    temp_state.state = "5.0"  # cold -> desire open (already open, but current is unknown)

    hass.states.get.side_effect = lambda entity_id: {
        MOCK_TEMP_SENSOR_ENTITY_ID: temp_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_SUN_ENTITY_ID: MagicMock(state="above_horizon", attributes={"elevation": 30.0, "azimuth": 180.0}),
    }.get(entity_id)

    await coordinator.async_refresh()

    # With temp-only config and cold reading, desired is open (100). Since current defaults to 100 when missing,
    # no movement is needed and no service call should be made.
    hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_direction_string_skips_cover_in_sun_only() -> None:
    """Invalid non-numeric direction should skip sun automation but allow temperature automation."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()

    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID], threshold=0)
    # Add temperature configuration for combined automation
    config[ConfKeys.TEMP_THRESHOLD.value] = 24.0
    config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = "south"  # invalid string
    entry = MockConfigEntry(config)

    coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, entry))

    cover_state = MagicMock()
    cover_state.entity_id = MOCK_COVER_ENTITY_ID
    cover_state.state = "open"
    cover_state.attributes = {
        ATTR_CURRENT_POSITION: 50,
        "supported_features": CoverEntityFeature.SET_POSITION,
    }

    sun_state = MagicMock()
    sun_state.entity_id = MOCK_SUN_ENTITY_ID
    sun_state.state = "above_horizon"
    sun_state.attributes = {"elevation": 50.0, "azimuth": 180.0}

    hass.states.get.side_effect = lambda entity_id: {
        MOCK_SUN_ENTITY_ID: sun_state,
        MOCK_COVER_ENTITY_ID: cover_state,
        MOCK_TEMP_SENSOR_ENTITY_ID: MagicMock(state="22.0"),  # Comfortable temp
    }.get(entity_id)

    await coordinator.async_refresh()
    result = coordinator.data

    # Cover should be skipped entirely due to invalid direction
    assert MOCK_COVER_ENTITY_ID not in result[ConfKeys.COVERS.value]

    # With comfortable temp and skipped cover, no service call expected
    hass.services.async_call.assert_not_called()
