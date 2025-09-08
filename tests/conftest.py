"""Common test utilities and fixtures for Smart Cover Automation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import CoverEntityFeature
from homeassistant.core import HomeAssistant

from custom_components.smart_cover_automation.const import DOMAIN
from custom_components.smart_cover_automation.settings import DEFAULTS, KEYS

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
        KEYS["COVERS"]: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        KEYS["MAX_TEMPERATURE"]: DEFAULTS["MAX_TEMPERATURE"],
        KEYS["MIN_TEMPERATURE"]: DEFAULTS["MIN_TEMPERATURE"],
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
        KEYS["COVERS"]: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        KEYS["SUN_ELEVATION_THRESHOLD"]: DEFAULTS["SUN_ELEVATION_THRESHOLD"],
        # Use numeric azimuths (degrees) for directions
        f"{MOCK_COVER_ENTITY_ID}_cover_direction": 180.0,
        f"{MOCK_COVER_ENTITY_ID_2}_cover_direction": 0.0,
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
    max_temp: float = DEFAULTS["MAX_TEMPERATURE"],
    min_temp: float = DEFAULTS["MIN_TEMPERATURE"],
) -> dict[str, Any]:
    """Create temperature automation config."""
    return {
        KEYS["COVERS"]: covers or [MOCK_COVER_ENTITY_ID],
        KEYS["MAX_TEMPERATURE"]: max_temp,
        KEYS["MIN_TEMPERATURE"]: min_temp,
    }


def create_sun_config(
    covers: list[str] | None = None,
    threshold: float = DEFAULTS["SUN_ELEVATION_THRESHOLD"],
) -> dict[str, Any]:
    """Create sun automation config."""
    config = {
        KEYS["COVERS"]: covers or [MOCK_COVER_ENTITY_ID],
        KEYS["SUN_ELEVATION_THRESHOLD"]: threshold,
    }
    # Add directions for each cover
    for cover in config[KEYS["COVERS"]]:
        # Default to south-facing (180°) as numeric azimuth
        config[f"{cover}_cover_direction"] = 180.0
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
