"""Common test utilities and fixtures for Smart Cover Automation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.core import HomeAssistant

from custom_components.smart_cover_automation.config import CONF_SPECS, ConfKeys
from custom_components.smart_cover_automation.const import DOMAIN

# Test data
MOCK_COVER_ENTITY_ID = "cover.test_cover"
MOCK_COVER_ENTITY_ID_2 = "cover.test_cover_2"
MOCK_TEMP_SENSOR_ENTITY_ID = "sensor.temperature"
MOCK_SUN_ENTITY_ID = "sun.sun"


@pytest.fixture(autouse=True)
def _quiet_logs(caplog: pytest.LogCaptureFixture) -> None:
    """Reduce log noise during tests while keeping logs available for assertions.

    Default to ERROR for our integration and Home Assistant; individual tests can
    raise levels with caplog.set_level when asserting on INFO/DEBUG messages.
    """
    import logging

    caplog.set_level(logging.ERROR, logger="custom_components.smart_cover_automation")
    caplog.set_level(logging.ERROR, logger="homeassistant")


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.config_entries = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.entry_id = "test_entry_id"
    entry.data = {
        ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        ConfKeys.MAX_TEMPERATURE.value: CONF_SPECS[ConfKeys.MAX_TEMPERATURE].default,
        ConfKeys.MIN_TEMPERATURE.value: CONF_SPECS[ConfKeys.MIN_TEMPERATURE].default,
    }
    entry.runtime_data = MagicMock()
    entry.runtime_data.config = entry.data
    return entry


@pytest.fixture
def mock_config_entry_sun() -> MagicMock:
    """Create a mock config entry for sun automation."""
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.entry_id = "test_entry_id_sun"
    entry.data = {
        ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: CONF_SPECS[ConfKeys.SUN_ELEVATION_THRESHOLD].default,
        # Use numeric azimuths (degrees) for directions
        f"{MOCK_COVER_ENTITY_ID}_cover_azimuth": 180.0,
        f"{MOCK_COVER_ENTITY_ID_2}_cover_azimuth": 0.0,
    }
    entry.runtime_data = MagicMock()
    entry.runtime_data.config = entry.data
    return entry


@pytest.fixture
def mock_cover_state() -> MagicMock:
    """Create a mock cover state."""
    state = MagicMock()
    state.entity_id = MOCK_COVER_ENTITY_ID
    state.state = "open"
    state.attributes = {
        "current_position": 100,
        "supported_features": CoverEntityFeature.SET_POSITION,
    }
    return state


@pytest.fixture
def mock_cover_state_2() -> MagicMock:
    """Create a mock cover state for second cover."""
    state = MagicMock()
    state.entity_id = MOCK_COVER_ENTITY_ID_2
    state.state = "closed"
    state.attributes = {
        "current_position": 0,
        "supported_features": CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
    }
    return state


@pytest.fixture
def mock_temperature_state() -> MagicMock:
    """Create a mock temperature sensor state."""
    state = MagicMock()
    state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID
    state.state = "22.5"
    state.attributes = {}
    return state


@pytest.fixture
def mock_sun_state() -> MagicMock:
    """Create a mock sun state."""
    state = MagicMock()
    state.entity_id = MOCK_SUN_ENTITY_ID
    state.state = "above_horizon"
    state.attributes = {
        "elevation": 35.0,
        "azimuth": 180.0,
    }
    return state


@pytest.fixture
def mock_unavailable_state() -> MagicMock:
    """Create a mock unavailable state."""
    state = MagicMock()
    state.state = "unavailable"
    state.attributes = {}
    return state


class MockConfigEntry:
    """Mock config entry for testing."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize mock config entry."""
        self.domain = DOMAIN
        self.entry_id = "test_entry"
        self.data = data
        self.runtime_data = MagicMock()
        self.runtime_data.config = data
        self.add_update_listener = MagicMock(return_value=MagicMock())
        self.async_on_unload = MagicMock()


def create_temperature_config(
    covers: list[str] | None = None,
    max_temp: float = CONF_SPECS[ConfKeys.MAX_TEMPERATURE].default,
    min_temp: float = CONF_SPECS[ConfKeys.MIN_TEMPERATURE].default,
) -> dict[str, Any]:
    """Create temperature automation config."""
    return {
        ConfKeys.COVERS.value: covers or [MOCK_COVER_ENTITY_ID],
        ConfKeys.MAX_TEMPERATURE.value: max_temp,
        ConfKeys.MIN_TEMPERATURE.value: min_temp,
    }


def create_sun_config(
    covers: list[str] | None = None,
    threshold: float = CONF_SPECS[ConfKeys.SUN_ELEVATION_THRESHOLD].default,
) -> dict[str, Any]:
    """Create sun automation config."""
    config = {
        ConfKeys.COVERS.value: covers or [MOCK_COVER_ENTITY_ID],
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: threshold,
    }
    # Add directions for each cover
    for cover in config[ConfKeys.COVERS.value]:
        # Default to south-facing (180°) as numeric azimuth
        config[f"{cover}_cover_azimuth"] = 180.0
    return config


async def assert_service_called(
    mock_services: MagicMock,
    domain: str,
    service: str,
    entity_id: str,
    **kwargs: Any,
) -> None:
    """Assert that a service was called with specific parameters."""
    mock_services.async_call.assert_called()
    calls = mock_services.async_call.call_args_list

    for call in calls:
        args, call_kwargs = call
        if args[0] == domain and args[1] == service and args[2]["entity_id"] == entity_id:
            for key, value in kwargs.items():
                expected_msg = f"Expected {key}={value}, got {args[2].get(key)}"
                if args[2].get(key) != value:
                    raise AssertionError(expected_msg)
            return

    actual_calls = [call.args for call in calls]
    pytest.fail(f"Service {domain}.{service} not called for {entity_id} with {kwargs}. Actual calls: {actual_calls}")
