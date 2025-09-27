"""Common test utilities and fixtures for Smart Cover Automation.

This file provides shared pytest fixtures, mock objects, and utility functions used
across all test modules. It centralizes test setup logic to avoid duplication and
ensure consistent test environments.

Key components:
- Mock Home Assistant instances and states
- Test data constants (entity IDs, thresholds)
- Configuration builders for different automation scenarios
- Service call assertion helpers
- Combined state mock builders for complex test scenarios
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES, Platform
from homeassistant.core import HomeAssistant

from custom_components.smart_cover_automation.config import CONF_SPECS, ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_POS_FULLY_CLOSED,
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
    DOMAIN,
    HA_WEATHER_COND_SUNNY,
)

# Test data constants - these provide consistent entity IDs across all tests
# Used for temperature-based and sun-based automation testing
MOCK_COVER_ENTITY_ID = "cover.test_cover"
MOCK_COVER_ENTITY_ID_2 = "cover.test_cover_2"
MOCK_WEATHER_ENTITY_ID = "weather.forecast"  # Now using weather entity for temperature
MOCK_SUN_ENTITY_ID = "sun.sun"

# Centralized test constants - shared across all test files to eliminate duplication
# These constants provide consistent values for automation testing scenarios

# Temperature test constants - realistic values for automation triggers
TEST_HOT_TEMP = "26.0"  # Temperature that triggers cover closing to block heat
TEST_COLD_TEMP = "18.0"  # Temperature that triggers cover opening for warmth
TEST_COMFORTABLE_TEMP_1 = "22.0"  # Neutral temperature (integration tests)
TEST_COMFORTABLE_TEMP_2 = "22.5"  # Neutral temperature (coordinator tests)

# Cover position test constants - standard positions for automation
TEST_COVER_OPEN = 100  # Fully open cover position (100%)
TEST_COVER_CLOSED = 0  # Fully closed cover position (0%)
TEST_PARTIAL_POSITION = 50  # Partially open cover position for testing

# Sun position test constants - realistic values for sun automation
TEST_HIGH_ELEVATION = 45.0  # Sun elevation above threshold (triggers automation)
TEST_LOW_ELEVATION = 15.0  # Sun elevation below threshold (no sun automation)
TEST_DIRECT_AZIMUTH = 180.0  # Sun azimuth directly hitting south-facing window
TEST_INDIRECT_AZIMUTH = 90.0  # Sun azimuth not hitting south-facing window
TEST_TILT_ANGLE = 20.0  # Cover tilt angle for testing tilt functionality
TEST_CLOSED_TILT_POSITION = 0  # Fully closed tilt position

# Multi-cover test constants - for concurrent control scenarios
TEST_NUM_COVERS = 3  # Number of covers used in concurrent control tests
TEST_MIN_SERVICE_CALLS = 2  # Minimum expected service calls for multi-cover scenarios


@pytest.fixture(autouse=True)
def _quiet_logs(caplog: pytest.LogCaptureFixture) -> None:
    """Reduce log noise during tests while keeping logs available for assertions.

    This fixture automatically applies to all tests (autouse=True) and sets
    log levels to ERROR to reduce noise in test output. Individual tests can
    override this by calling caplog.set_level() when they need to assert on
    specific log messages at INFO or DEBUG levels.

    Default to ERROR for our integration and Home Assistant; individual tests can
    raise levels with caplog.set_level when asserting on INFO/DEBUG messages.
    """
    import logging

    caplog.set_level(logging.ERROR, logger="custom_components.smart_cover_automation")
    caplog.set_level(logging.ERROR, logger="homeassistant")


# Global variable to store current temperature for weather service mock
_CURRENT_WEATHER_TEMP = 25.0


def set_weather_forecast_temp(temp: float) -> None:
    """Set the temperature that the weather service mock will return."""
    global _CURRENT_WEATHER_TEMP
    _CURRENT_WEATHER_TEMP = temp


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock HomeAssistant instance.

    Provides a fully mocked Home Assistant core instance with:
    - Mock states registry for entity state management
    - Mock services registry for service call testing
    - Mock config_entries for integration configuration
    - Mock weather forecast service for temperature data

    This is the foundation for most integration tests.
    """
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.config_entries = MagicMock()

    # Mock weather forecast service call
    async def mock_weather_service(domain, service, service_data, **kwargs):
        """Mock weather forecast service that returns temperature data."""
        if domain == Platform.WEATHER and service == "get_forecasts":
            entity_id = service_data.get("entity_id", "weather.forecast")
            return {
                entity_id: {
                    "forecast": [
                        {
                            "datetime": datetime.now(timezone.utc).isoformat(),
                            "native_temperature": _CURRENT_WEATHER_TEMP,
                            "temp_max": _CURRENT_WEATHER_TEMP,
                        }
                    ]
                }
            }
        return {}

    hass.services.async_call = AsyncMock(side_effect=mock_weather_service)
    # Store reference to allow temperature override in tests
    hass._weather_service_mock = mock_weather_service
    return hass


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry for temperature-based automation.

    Provides a standard configuration entry with:
    - Two test covers for automation
    - Default temperature threshold from configuration specs
    - Proper domain and entry ID setup
    - Runtime data structure matching integration expectations
    """
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
    """Create a mock config entry for sun-based automation.

    Provides a sun automation configuration with:
    - Two test covers with different azimuths (south and north facing)
    - Default sun elevation threshold from configuration specs
    - Numeric azimuth values in degrees for proper direction calculation
    - Separate entry ID to avoid conflicts with temperature automation tests
    """
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
    """Create a mock cover state for the primary test cover.

    Provides a cover state representing:
    - Fully open position (100%)
    - Support for position-based control (SET_POSITION feature)
    - Standard cover entity attributes for automation testing
    """
    state = MagicMock()
    state.entity_id = MOCK_COVER_ENTITY_ID
    state.state = "open"
    state.attributes = {
        ATTR_CURRENT_POSITION: COVER_POS_FULLY_OPEN,
        ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
    }
    return state


@pytest.fixture
def mock_cover_state_2() -> MagicMock:
    """Create a mock cover state for the secondary test cover.

    Provides a second cover with different characteristics:
    - Fully closed position (0%) for testing diverse scenarios
    - Basic open/close control only (no position support)
    - Used for testing multi-cover automation logic
    """
    state = MagicMock()
    state.entity_id = MOCK_COVER_ENTITY_ID_2
    state.state = "closed"
    state.attributes = {
        ATTR_CURRENT_POSITION: COVER_POS_FULLY_CLOSED,
        ATTR_SUPPORTED_FEATURES: CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE,
    }
    return state


@pytest.fixture
def mock_temperature_state() -> MagicMock:
    """Create a mock temperature sensor state.

    Provides a temperature sensor with:
    - Moderate temperature (22.5°C) for threshold testing
    - Standard sensor state structure for automation logic
    """
    state = MagicMock()
    state.entity_id = MOCK_WEATHER_ENTITY_ID
    state.state = TEST_COMFORTABLE_TEMP_2
    state.attributes = {}
    return state


@pytest.fixture
def mock_sun_state() -> MagicMock:
    """Create a mock sun state for sun-based automation testing.

    Provides sun sensor with:
    - Above horizon state for active sun automation
    - Elevation and azimuth attributes for position calculation
    - South-facing direction (180°) and moderate elevation (35°)
    """
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
    """Create a mock unavailable state for error condition testing.

    Used to simulate sensor/entity unavailability scenarios:
    - State set to "unavailable" (Home Assistant standard)
    - Empty attributes dict for realistic unavailable entity behavior
    """
    state = MagicMock()
    state.state = "unavailable"
    state.attributes = {}
    return state


class MockConfigEntry:
    """Mock config entry for testing integration configuration scenarios.

    Provides a lightweight mock of Home Assistant's ConfigEntry class with:
    - Standard domain and entry ID attributes
    - Runtime data structure for configuration access
    - Mock methods for listener management and lifecycle hooks

    This is used when tests need more control over config entry behavior
    than the standard fixtures provide.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize mock config entry with configuration data.

        Args:
            data: Configuration dictionary matching integration schema
        """
        self.domain = DOMAIN
        self.entry_id = "test_entry"
        self.data = data
        self.runtime_data = MagicMock()
        self.runtime_data.config = data
        self.add_update_listener = MagicMock(return_value=MagicMock())
        self.async_on_unload = MagicMock()
        self.hass = MagicMock()
        self.hass.states = MagicMock()


def create_sun_config(
    covers: list[str] | None = None,
    threshold: float = CONF_SPECS[ConfKeys.SUN_ELEVATION_THRESHOLD].default,
) -> dict[str, Any]:
    """Create a configuration dictionary for sun-based automation.

    Builds a complete configuration with both sun and temperature settings
    since the integration now requires both automation types to be configured.

    Args:
        covers: List of cover entity IDs to automate (defaults to single test cover)
        threshold: Sun elevation threshold in degrees (defaults to config spec)

    Returns:
        Complete configuration dictionary with sun settings and default temperature settings
    """
    config = {
        ConfKeys.COVERS.value: covers or [MOCK_COVER_ENTITY_ID],
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: threshold,
        # Since both automations are now always configured, include temp defaults
        ConfKeys.TEMP_THRESHOLD.value: CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
        ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,  # Use weather entity
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
    """Create a configuration dictionary for temperature-based automation.

    Builds a complete configuration with both temperature and sun settings
    since the integration now requires both automation types to be configured.

    Args:
        covers: List of cover entity IDs to automate (defaults to single test cover)
        temp_threshold: Temperature threshold in Celsius (defaults to config spec)

    Returns:
        Complete configuration dictionary with temperature settings and default sun settings
    """
    config = {
        ConfKeys.COVERS.value: covers or [MOCK_COVER_ENTITY_ID],
        ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,  # Use weather entity for temperature
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
    """Helper function to assert that a specific service was called with expected parameters.

    This utility searches through all service calls made during a test to verify
    that a specific service was called with the correct parameters. This is essential
    for testing automation behavior where covers are controlled via service calls.

    Args:
        mock_services: Mock services registry from Home Assistant
        domain: Service domain (e.g., "cover", "switch")
        service: Service name (e.g., "set_cover_position", "turn_on")
        entity_id: Target entity ID for the service call
        **kwargs: Additional service parameters to verify (e.g., position=50)

    Raises:
        AssertionError: If the expected service call was not found
    """
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
    sun_elevation: float = 50.0,
    sun_azimuth: float = 180.0,
    cover_states: dict[str, dict[str, Any]] | None = None,
) -> dict[str, MagicMock]:
    """Create a comprehensive state mock with both temperature and sun sensors.

    This helper function addresses the new requirement that both automation types
    are always configured, so all tests need both sensor states available. It builds
    a complete entity state mapping for use with hass.states.get.side_effect.

    Note: Temperature is now set globally via set_weather_forecast_temp() before calling this function.

    Args:
        sun_elevation: Sun elevation attribute in degrees
        sun_azimuth: Sun azimuth attribute in degrees
        cover_states: Optional dict mapping cover entity IDs to their state attributes

    Returns:
        Dict mapping entity IDs to their mock states for use in hass.states.get.side_effect
    """
    # Weather entity state (now using weather instead of temperature sensor)
    weather_mock = MagicMock()
    weather_mock.entity_id = MOCK_WEATHER_ENTITY_ID
    weather_mock.state = HA_WEATHER_COND_SUNNY

    # Sun sensor state
    sun_mock = MagicMock()
    sun_mock.entity_id = MOCK_SUN_ENTITY_ID
    sun_mock.attributes = {"elevation": sun_elevation, "azimuth": sun_azimuth}

    # Build the state mapping
    state_mapping = {
        MOCK_WEATHER_ENTITY_ID: weather_mock,
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
            ATTR_CURRENT_POSITION: COVER_POS_FULLY_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        state_mapping[MOCK_COVER_ENTITY_ID] = cover_mock

    return state_mapping


def create_combined_and_scenario(
    cover_id: str = MOCK_COVER_ENTITY_ID,
    current_position: int = COVER_POS_FULLY_OPEN,
    temp_hot: bool = True,
    sun_hitting: bool = True,
    covers_max_closure: int = COVER_POS_FULLY_OPEN,
    covers_min_closure: int = COVER_POS_FULLY_CLOSED,
) -> tuple[dict[str, Any], dict[str, MagicMock]]:
    """Create a scenario for testing combined temperature AND sun automation logic.

    Since both automation types are always active, this helper creates scenarios
    where both temp_hot and sun_hitting must be true for covers to close. This is
    essential for testing the integration's AND logic behavior.

    Args:
        cover_id: Cover entity ID to test with
        current_position: Current cover position (COVER_POS_FULLY_CLOSED=closed, COVER_POS_FULLY_OPEN=open)
        temp_hot: Whether temperature should be above threshold (>24°C)
        sun_hitting: Whether sun should be hitting the window (matching azimuth)
        covers_max_closure: Maximum closure percentage (0-100)
        covers_min_closure: Minimum closure percentage (0-100)

    Returns:
        Tuple of (configuration_dict, state_mapping_dict) ready for test setup
    """
    # Create config with both temperature and sun automation
    config = {
        ConfKeys.COVERS.value: [cover_id],
        ConfKeys.TEMP_THRESHOLD.value: 23.0,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
        ConfKeys.COVERS_MAX_CLOSURE.value: covers_max_closure,
        ConfKeys.COVERS_MIN_CLOSURE.value: covers_min_closure,
        f"{cover_id}_{COVER_SFX_AZIMUTH}": 180.0,
    }

    # Set temperature based on temp_hot flag
    temp_value = TEST_HOT_TEMP if temp_hot else TEST_COMFORTABLE_TEMP_1
    # Set the weather forecast temperature globally
    set_weather_forecast_temp(float(temp_value))

    # Set sun position based on sun_hitting flag
    sun_azimuth = 180.0 if sun_hitting else 90.0  # 180° hits window, 90° misses

    # Create state mapping
    state_mapping = create_combined_state_mock(
        sun_elevation=45.0,  # Above threshold
        sun_azimuth=sun_azimuth,
        cover_states={
            cover_id: {
                ATTR_CURRENT_POSITION: current_position,
                ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            }
        },
    )

    return config, state_mapping
