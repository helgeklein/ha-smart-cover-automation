"""Extra tests to increase coverage for coordinator branches."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import CoverEntityFeature

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
    MockConfigEntry,
    assert_service_called,
    create_sun_config,
    create_temperature_config,
)


@pytest.mark.asyncio
async def test_automation_disabled_skips_actions(
    mock_hass: MagicMock,
) -> None:
    """When enabled is False, coordinator returns empty covers and takes no action."""
    config = create_temperature_config(covers=[MOCK_COVER_ENTITY_ID])
    config[ConfKeys.ENABLED.value] = False
    config_entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

    await coordinator.async_refresh()
    assert coordinator.data == {ConfKeys.COVERS.value: {}}
    mock_hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_open_cover_without_position_support_when_cold(
    mock_hass: MagicMock,
) -> None:
    """If too cold and cover lacks position support, open_cover service should be used."""
    config = create_temperature_config(covers=[MOCK_COVER_ENTITY_ID])
    config_entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

    # Cover supports only open/close; currently closed
    cover_state = MagicMock()
    cover_state.attributes = {
        "current_position": 0,
        "supported_features": CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
    }

    # Temperature below minimum threshold to trigger opening
    temp_state = MagicMock()
    temp_state.state = "18.0"

    mock_hass.states.get.side_effect = lambda entity_id: {
        "sensor.temperature": temp_state,
        MOCK_COVER_ENTITY_ID: cover_state,
    }.get(entity_id)

    await coordinator.async_refresh()

    await assert_service_called(mock_hass.services, "cover", "open_cover", MOCK_COVER_ENTITY_ID)


@pytest.mark.asyncio
async def test_min_position_delta_skips_small_adjustments(
    mock_hass: MagicMock,
) -> None:
    """Small desired change below min_position_delta should be skipped (pass branch)."""
    # Sun-only config with very small max closure to produce desired=95 from 100
    config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
    config[ConfKeys.MIN_POSITION_DELTA.value] = 10  # require >=10 change
    config[ConfKeys.MAX_CLOSURE.value] = 5  # desired position = 100 - 5 = 95
    config_entry = MockConfigEntry(config)
    coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

    # Sun above threshold, direct at window
    sun_state = MagicMock()
    sun_state.attributes = {"elevation": 45.0, "azimuth": 180.0}

    # Cover supports position and starts fully open (100)
    cover_state = MagicMock()
    cover_state.attributes = {
        "current_position": 100,
        "supported_features": CoverEntityFeature.SET_POSITION,
    }

    mock_hass.states.get.side_effect = lambda entity_id: {
        MOCK_SUN_ENTITY_ID: sun_state,
        MOCK_COVER_ENTITY_ID: cover_state,
    }.get(entity_id)

    await coordinator.async_refresh()
    result = coordinator.data
    assert result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]["desired_position"] == 95
    # Movement from 100 to 95 is below min_position_delta -> no service called
    mock_hass.services.async_call.assert_not_called()
