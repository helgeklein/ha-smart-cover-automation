"""Common test utilities and fixtures for Smart Cover Automation."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.core import HomeAssistant

from custom_components.smart_cover_automation.config import CONF_SPECS, ConfKeys
from custom_components.smart_cover_automation.const import COVER_SFX_AZIMUTH, DOMAIN

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
        ConfKeys.TEMP_THRESHOLD.value: CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
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
        f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}": 180.0,
        f"{MOCK_COVER_ENTITY_ID_2}_{COVER_SFX_AZIMUTH}": 0.0,
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
        ATTR_CURRENT_POSITION: 100,
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
        ATTR_CURRENT_POSITION: 0,
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


def create_sun_config(
    covers: list[str] | None = None,
    threshold: float = CONF_SPECS[ConfKeys.SUN_ELEVATION_THRESHOLD].default,
) -> dict[str, Any]:
    """Create sun automation config."""
    config = {
        ConfKeys.COVERS.value: covers or [MOCK_COVER_ENTITY_ID],
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: threshold,
        # Since both automations are now always configured, include temp defaults
        ConfKeys.TEMP_THRESHOLD.value: CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
    }
    # Add directions for each cover
    for cover in config[ConfKeys.COVERS.value]:
        # Default to south-facing (180°) as numeric azimuth
        config[f"{cover}_{COVER_SFX_AZIMUTH}"] = 180.0
    return config


def create_temperature_config(
    covers: list[str] | None = None,
    temp_threshold: float = CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
) -> dict[str, Any]:
    """Create temperature automation config."""
    config = {
        ConfKeys.COVERS.value: covers or [MOCK_COVER_ENTITY_ID],
        ConfKeys.TEMP_THRESHOLD.value: temp_threshold,
        # Since both automations are now always configured, include sun defaults
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: CONF_SPECS[ConfKeys.SUN_ELEVATION_THRESHOLD].default,
    }
    # Add directions for each cover (needed for sun automation)
    for cover in config[ConfKeys.COVERS.value]:
        # Default to south-facing (180°) as numeric azimuth
        config[f"{cover}_{COVER_SFX_AZIMUTH}"] = 180.0
    return config


async def assert_service_called(
    mock_services: MagicMock,
    domain: str,
    service: str,
    entity_id: str,
    **kwargs: Any,
) -> None:
    """Helper to assert service was called with specific parameters."""
    mock_services.async_call.assert_called()
    # Find the call that matches our criteria
    found_call = False
    for call in mock_services.async_call.call_args_list:
        args, call_kwargs = call
        # Handle both string domain and Platform enum
        actual_domain = str(args[0]) if hasattr(args[0], "value") else args[0]
        if len(args) >= 2 and actual_domain == domain and args[1] == service:
            # Get service data (could be args[2] or in call_kwargs)
            service_data = args[2] if len(args) > 2 else call_kwargs
            if service_data.get("entity_id") == entity_id:
                # Check additional kwargs match
                if all(service_data.get(k) == v for k, v in kwargs.items()):
                    found_call = True
                    break

    if not found_call:
        raise AssertionError(
            f"Service call {domain}.{service} with entity_id={entity_id} and kwargs={kwargs} not found in {mock_services.async_call.call_args_list}"
        )


def create_combined_state_mock(
    temp_state: str = "22.0",
    sun_elevation: float = 50.0,
    sun_azimuth: float = 180.0,
    cover_states: dict[str, dict[str, Any]] | None = None,
) -> dict[str, MagicMock]:
    """Create a comprehensive state mock with both temperature and sun sensors.

    This helper function addresses the new requirement that both automation types
    are always configured, so all tests need both sensor states.

    Args:
        temp_state: Temperature sensor state value
        sun_elevation: Sun elevation attribute
        sun_azimuth: Sun azimuth attribute
        cover_states: Dict mapping cover entity IDs to their state attributes

    Returns:
        Dict mapping entity IDs to their mock states for use in hass.states.get.side_effect
    """
    # Temperature sensor state
    temp_mock = MagicMock()
    temp_mock.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID
    temp_mock.state = temp_state

    # Sun sensor state
    sun_mock = MagicMock()
    sun_mock.entity_id = MOCK_SUN_ENTITY_ID
    sun_mock.attributes = {"elevation": sun_elevation, "azimuth": sun_azimuth}

    # Build the state mapping
    state_mapping = {
        MOCK_TEMP_SENSOR_ENTITY_ID: temp_mock,
        MOCK_SUN_ENTITY_ID: sun_mock,
    }

    # Add cover states if provided
    if cover_states:
        for entity_id, attributes in cover_states.items():
            cover_mock = MagicMock()
            cover_mock.entity_id = entity_id
            cover_mock.attributes = attributes
            state_mapping[entity_id] = cover_mock
    else:
        # Add default cover
        cover_mock = MagicMock()
        cover_mock.entity_id = MOCK_COVER_ENTITY_ID
        cover_mock.attributes = {
            ATTR_CURRENT_POSITION: 100,
            "supported_features": CoverEntityFeature.SET_POSITION,
        }
        state_mapping[MOCK_COVER_ENTITY_ID] = cover_mock

    return state_mapping


def create_combined_and_scenario(
    cover_id: str = MOCK_COVER_ENTITY_ID,
    current_position: int = 100,
    temp_hot: bool = True,
    sun_hitting: bool = True,
    covers_max_closure: int = 100,
) -> tuple[dict[str, Any], dict[str, MagicMock]]:
    """Create a scenario for combined AND logic testing.

    Since both automations are always active, this helper creates scenarios
    where both temp_hot and sun_hitting must be true for covers to close.

    Args:
        cover_id: Cover entity ID
        current_position: Current cover position
        temp_hot: Whether temperature should be hot (>24°C)
        sun_hitting: Whether sun should be hitting the window
        covers_max_closure: Maximum closure percentage

    Returns:
        Tuple of (config, state_mapping)
    """
    # Create config with both temperature and sun automation
    config = {
        ConfKeys.COVERS.value: [cover_id],
        ConfKeys.TEMP_THRESHOLD.value: 23.0,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
        ConfKeys.COVERS_MAX_CLOSURE.value: covers_max_closure,
        f"{cover_id}_{COVER_SFX_AZIMUTH}": 180.0,
    }

    # Set temperature based on temp_hot flag
    temp_value = "25.0" if temp_hot else "22.0"

    # Set sun position based on sun_hitting flag
    sun_azimuth = 180.0 if sun_hitting else 90.0  # 180° hits window, 90° misses

    # Create state mapping
    state_mapping = create_combined_state_mock(
        temp_state=temp_value,
        sun_elevation=45.0,  # Above threshold
        sun_azimuth=sun_azimuth,
        cover_states={
            cover_id: {
                ATTR_CURRENT_POSITION: current_position,
                "supported_features": CoverEntityFeature.SET_POSITION,
            }
        },
    )

    return config, state_mapping
