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
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES, Platform
from homeassistant.core import HomeAssistant

from custom_components.smart_cover_automation.config import CONF_SPECS, ConfKeys

if TYPE_CHECKING:
    from custom_components.smart_cover_automation.config_flow import FlowHandler
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
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
    hass = create_mock_hass_with_weather_service()
    hass.config_entries = MagicMock()
    return hass


def create_mock_config_entry(data: dict[str, Any], entry_id: str = "test_entry_id") -> MagicMock:
    """Create a standard mock config entry with consistent structure.

    Args:
        data: Configuration data dictionary
        entry_id: Unique identifier for the entry (default: "test_entry_id")

    Returns:
        Mock config entry with standard domain, ID, and runtime data structure
    """
    entry = MagicMock()
    entry.domain = DOMAIN
    entry.entry_id = entry_id
    entry.data = data
    entry.runtime_data = MagicMock()
    entry.runtime_data.config = data
    return entry


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry for temperature-based automation.

    Provides a standard configuration entry with:
    - Two test covers for automation
    - Default temperature threshold from configuration specs
    - Proper domain and entry ID setup
    - Runtime data structure matching integration expectations
    """
    data = {
        ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        ConfKeys.TEMP_THRESHOLD.value: CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
    }
    return create_mock_config_entry(data, "test_entry_id")


@pytest.fixture
def mock_config_entry_sun() -> MagicMock:
    """Create a mock config entry for sun-based automation.

    Provides a sun automation configuration with:
    - Two test covers with different azimuths (south and north facing)
    - Default sun elevation threshold from configuration specs
    - Numeric azimuth values in degrees for proper direction calculation
    - Separate entry ID to avoid conflicts with temperature automation tests
    """
    data = {
        ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: CONF_SPECS[ConfKeys.SUN_ELEVATION_THRESHOLD].default,
        # Use numeric azimuths (degrees) for directions
        f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}": 180.0,
        f"{MOCK_COVER_ENTITY_ID_2}_{COVER_SFX_AZIMUTH}": 0.0,
    }
    return create_mock_config_entry(data, "test_entry_id_sun")


@pytest.fixture
def mock_cover_state() -> MagicMock:
    """Create a mock cover state for the primary test cover.

    Provides a cover state representing:
    - Fully open position (100%)
    - Support for position-based control (SET_POSITION feature)
    - Standard cover entity attributes for automation testing
    """
    return create_standard_cover_state(
        entity_id=MOCK_COVER_ENTITY_ID, position=COVER_POS_FULLY_OPEN, features=CoverEntityFeature.SET_POSITION
    )


@pytest.fixture
def mock_cover_state_2() -> MagicMock:
    """Create a mock cover state for the secondary test cover.

    Provides a second cover with different characteristics:
    - Fully closed position (0%) for testing diverse scenarios
    - Basic open/close control only (no position support)
    - Used for testing multi-cover automation logic
    """
    return create_standard_cover_state(
        entity_id=MOCK_COVER_ENTITY_ID_2, position=COVER_POS_FULLY_CLOSED, features=CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )


@pytest.fixture
def mock_temperature_state() -> MagicMock:
    """Create a mock temperature sensor state.

    Provides a temperature sensor with:
    - Moderate temperature (22.5°C) for threshold testing
    - Standard sensor state structure for automation logic
    """
    return create_standard_weather_state(condition=TEST_COMFORTABLE_TEMP_2)


@pytest.fixture
def mock_sun_state() -> MagicMock:
    """Create a mock sun state for sun-based automation testing.

    Provides sun sensor with:
    - Above horizon state for active sun automation
    - Elevation and azimuth attributes for position calculation
    - South-facing direction (180°) and moderate elevation (35°)
    """
    return create_standard_sun_state(elevation=35.0, azimuth=180.0)


def create_unavailable_state() -> MagicMock:
    """Create a mock unavailable state for error condition testing.

    Returns:
        Mock state representing an unavailable entity
    """
    state = MagicMock()
    state.state = "unavailable"
    state.attributes = {}
    return state


@pytest.fixture
def mock_unavailable_state() -> MagicMock:
    """Create a mock unavailable state for error condition testing.

    Used to simulate sensor/entity unavailability scenarios:
    - State set to "unavailable" (Home Assistant standard)
    - Empty attributes dict for realistic unavailable entity behavior
    """
    return create_unavailable_state()


@pytest.fixture
def coordinator(mock_hass) -> "DataUpdateCoordinator":
    """Create a DataUpdateCoordinator instance configured for temperature automation.

    Provides a standard coordinator for most tests that need basic temperature
    automation functionality. This consolidates the duplicate coordinator fixtures
    found across multiple test files.

    Returns:
        DataUpdateCoordinator configured with temperature automation
    """
    from typing import cast

    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
    from custom_components.smart_cover_automation.data import IntegrationConfigEntry

    config = create_temperature_config()
    config_entry = MockConfigEntry(config)
    return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))


@pytest.fixture
def sun_coordinator(mock_hass) -> "DataUpdateCoordinator":
    """Create a DataUpdateCoordinator instance configured for sun automation.

    Provides a coordinator with sun automation configuration for testing
    sun-based cover control logic including azimuth and elevation thresholds.

    Returns:
        DataUpdateCoordinator configured with sun automation
    """
    from typing import cast

    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
    from custom_components.smart_cover_automation.data import IntegrationConfigEntry

    config = create_sun_config()
    config_entry = MockConfigEntry(config)
    return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))


@pytest.fixture
def simulation_coordinator(mock_hass) -> "DataUpdateCoordinator":
    """Create a coordinator with simulation mode enabled.

    Returns a coordinator configured for temperature automation with simulation
    mode enabled to test that cover commands are not actually sent.

    Returns:
        DataUpdateCoordinator with simulation mode enabled
    """
    from typing import cast

    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
    from custom_components.smart_cover_automation.data import IntegrationConfigEntry

    config = create_temperature_config()
    # Enable simulation mode
    config[ConfKeys.SIMULATION_MODE.value] = True
    config_entry = MockConfigEntry(config)
    return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))


@pytest.fixture
def flow_handler() -> "FlowHandler":
    """Create a fresh FlowHandler instance for testing.

    Provides a clean FlowHandler instance for each test method to ensure
    test isolation and prevent state leakage between tests. This consolidates
    the duplicate flow_handler fixtures found in config flow test files.

    Returns:
        New FlowHandler instance ready for testing
    """
    from custom_components.smart_cover_automation.config_flow import FlowHandler

    return FlowHandler()


def create_integration_coordinator(covers: list[str] | None = None) -> "DataUpdateCoordinator":
    """Create a coordinator specifically configured for integration testing.

    Provides a DataUpdateCoordinator with:
    - Mock Home Assistant instance with weather service
    - Temperature automation configuration
    - Optional custom cover list
    - Ready for comprehensive integration testing scenarios

    Args:
        covers: Optional list of cover entity IDs. Defaults to single test cover.

    Returns:
        DataUpdateCoordinator configured for integration testing
    """
    from typing import cast

    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
    from custom_components.smart_cover_automation.data import IntegrationConfigEntry

    hass = create_mock_hass_with_weather_service()
    hass.config_entries = MagicMock()

    config = create_temperature_config(covers=covers)
    config_entry = MockConfigEntry(config)
    return DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))


@pytest.fixture
def mock_hass_with_covers() -> MagicMock:
    """Create mock Home Assistant instance with valid cover and weather entities.

    Provides a mocked Home Assistant instance that simulates the presence
    of cover and weather entities in the state registry. This allows tests to validate
    configuration flow behavior with existing entities without
    requiring a full Home Assistant setup.

    The mock returns:
    - A "closed" state for entity IDs starting with "cover."
    - A weather state with daily forecast support for entity IDs starting with "weather."
    - None for all other entity IDs

    Returns:
        Mock Home Assistant instance with cover and weather entity simulation
    """

    def mock_get_state(entity_id: str) -> MagicMock | None:
        if entity_id.startswith("cover."):
            return MagicMock(state="closed")
        if entity_id.startswith("weather."):
            weather_state = MagicMock()
            weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}
            return weather_state
        return None

    hass = MagicMock()
    hass.states.get.side_effect = mock_get_state
    return hass


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
        self.options = {}  # Add options attribute for config persistence
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
    cover_list = [MOCK_COVER_ENTITY_ID] if covers is None else covers
    config = {
        ConfKeys.COVERS.value: cover_list,
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
            cover_mock.state = "open"  # Set a valid cover state
            cover_mock.attributes = attributes
            state_mapping[entity_id] = cover_mock
    else:
        # Add default cover
        cover_mock = MagicMock()
        cover_mock.entity_id = MOCK_COVER_ENTITY_ID
        cover_mock.state = "open"  # Set a valid cover state
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


# Consolidated weather service mock to eliminate duplication across test files
def create_mock_weather_service():
    """Create a standardized mock weather forecast service.

    This consolidates the duplicate mock_weather_service functions found across
    multiple test files into a single reusable implementation.

    Returns:
        Mock weather service function that can be used with AsyncMock
    """

    async def mock_weather_service(domain, service, service_data, **kwargs):
        """Mock weather forecast service that returns temperature data."""
        if domain == Platform.WEATHER and service == "get_forecasts":
            entity_id = service_data.get("entity_id", MOCK_WEATHER_ENTITY_ID)
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

    return mock_weather_service


def create_mock_state_getter(**entity_states: Any):
    """Create a standardized mock state getter function.

    This consolidates the duplicate mock_get_state functions found across
    multiple test files into a single reusable implementation.

    Args:
        **entity_states: Keyword arguments mapping entity IDs to their state objects

    Returns:
        Mock state getter function that can be used with side_effect

    Example:
        hass.states.get.side_effect = create_mock_state_getter(
            "cover.test": cover_state,
            "weather.test": weather_state
        )
    """

    def mock_get_state(entity_id: str) -> MagicMock | None:
        return entity_states.get(entity_id)

    return mock_get_state


def create_weather_service_with_cover_error(cover_error_type: type[Exception], *error_args):
    """Create weather service mock that simulates cover service errors.

    This consolidates the duplicate weather service + cover error simulation patterns
    found in error handling tests.

    Args:
        cover_error_type: Type of exception to raise for cover service calls
        *error_args: Arguments to pass to the exception constructor

    Returns:
        Mock weather service function that provides weather data but fails on cover calls
    """

    async def mock_weather_service(domain, service, service_data, **kwargs):
        if domain == "weather":
            # Get current temperature from global variable
            return {
                service_data.get("entity_id", "weather.forecast"): {
                    "forecast": [
                        {
                            "datetime": datetime.now(timezone.utc).isoformat(),
                            "native_temperature": _CURRENT_WEATHER_TEMP,
                            "temp_max": _CURRENT_WEATHER_TEMP,
                        }
                    ]
                }
            }
        else:
            # Simulate cover service call failure
            raise cover_error_type(*error_args)

    return mock_weather_service


def create_invalid_weather_service(invalid_data: list[dict[str, Any]]):
    """Create weather service mock that returns invalid or missing data.

    This consolidates weather service mocks used for testing error conditions
    like missing temperature fields or invalid data types.

    Args:
        invalid_data: List of forecast entries with invalid/missing data

    Returns:
        Mock weather service function that returns invalid weather data
    """

    async def mock_weather_service(domain, service, service_data, **kwargs):
        return {service_data.get("entity_id", "weather.forecast"): {"forecast": invalid_data}}

    return mock_weather_service


def create_standard_weather_state(condition: str = "sunny") -> MagicMock:
    """Create a standard weather state mock with common settings.

    Args:
        condition: Weather condition (default: "sunny")

    Returns:
        Mock weather state with standard attributes
    """
    weather_state = MagicMock()
    weather_state.state = condition
    weather_state.entity_id = MOCK_WEATHER_ENTITY_ID
    weather_state.attributes = {}
    return weather_state


def create_standard_sun_state(elevation: float = 45.0, azimuth: float = 180.0) -> MagicMock:
    """Create a standard sun state mock with common settings.

    Args:
        elevation: Sun elevation in degrees (default: 45.0)
        azimuth: Sun azimuth in degrees (default: 180.0 - south)

    Returns:
        Mock sun state with standard attributes
    """
    sun_state = MagicMock()
    sun_state.state = "above_horizon"
    sun_state.entity_id = MOCK_SUN_ENTITY_ID
    sun_state.attributes = {"elevation": elevation, "azimuth": azimuth}
    return sun_state


def create_standard_cover_state(entity_id: str = MOCK_COVER_ENTITY_ID, position: int = 100, features: int = 15) -> MagicMock:
    """Create a standard cover state mock with common settings.

    Args:
        entity_id: Cover entity ID (default: MOCK_COVER_ENTITY_ID)
        position: Current position 0-100 (default: 100 - fully open)
        features: Supported features bitmask (default: 15 - full support)

    Returns:
        Mock cover state with standard attributes
    """
    cover_state = MagicMock()
    cover_state.entity_id = entity_id
    cover_state.state = "open" if position > 0 else "closed"
    cover_state.attributes = {
        ATTR_CURRENT_POSITION: position,
        ATTR_SUPPORTED_FEATURES: features,
    }
    return cover_state


@pytest.fixture
def mock_config_entry_extended() -> MagicMock:
    """Create a mock config entry for extended testing scenarios.

    This consolidates the duplicate mock_config_entry fixtures found in
    test_config_flow_extended.py and provides a more comprehensive configuration
    for testing complex scenarios.

    Returns:
        Mock config entry with comprehensive data and options
    """
    config_entry = MagicMock()
    config_entry.data = {
        ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
        ConfKeys.TEMP_THRESHOLD.value: CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: CONF_SPECS[ConfKeys.SUN_ELEVATION_THRESHOLD].default,
    }
    config_entry.options = {
        f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}": 180.0,
        f"{MOCK_COVER_ENTITY_ID_2}_{COVER_SFX_AZIMUTH}": 90.0,
    }
    config_entry.hass = MagicMock()
    config_entry.hass.states = MagicMock()
    return config_entry


@pytest.fixture
def mock_hass_with_weather_and_covers() -> MagicMock:
    """Create mock Home Assistant instance with weather and cover entities.

    This consolidates the duplicate mock_hass_with_entities fixtures found across
    multiple test files and provides comprehensive entity simulation.

    Returns:
        Mock Home Assistant instance with simulated weather and cover entities
    """
    hass = MagicMock()

    def mock_get_state(entity_id: str) -> MagicMock | None:
        if entity_id.startswith("cover."):
            state = MagicMock()
            state.name = f"Test Cover {entity_id.split('.')[-1]}"
            state.state = "closed"
            state.attributes = {
                ATTR_CURRENT_POSITION: TEST_COVER_CLOSED,
                ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            }
            return state
        elif entity_id.startswith("weather."):
            state = MagicMock()
            state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}
            return state
        elif entity_id == MOCK_SUN_ENTITY_ID:
            state = MagicMock()
            state.state = "above_horizon"
            state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
            return state
        return None

    hass.states.get.side_effect = mock_get_state
    return hass


async def capture_platform_entities(hass: HomeAssistant, config: dict[str, Any], platform_name: str = "sensor") -> list[Any]:
    """Helper function to set up a platform and capture created entities.

    This consolidates the duplicate _capture_entities functions found across
    multiple test files into a single reusable implementation.

    Args:
        hass: Mock Home Assistant instance
        config: Configuration dictionary for the integration
        platform_name: Name of the platform to set up ("sensor", "binary_sensor", "switch")

    Returns:
        List of entities created by the platform
    """
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
    from custom_components.smart_cover_automation.data import IntegrationConfigEntry

    hass_mock = cast(MagicMock, hass)
    entry = MockConfigEntry(config)

    # Setup coordinator with basic successful state
    coordinator = DataUpdateCoordinator(hass_mock, cast(IntegrationConfigEntry, entry))
    coordinator.data = {"covers": {}}
    coordinator.last_update_success = True  # type: ignore[attr-defined]

    # Store coordinator in runtime data
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinator = coordinator

    # Import and call the appropriate platform setup function
    if platform_name == "sensor":
        from custom_components.smart_cover_automation.sensor import async_setup_entry
    elif platform_name == "binary_sensor":
        from custom_components.smart_cover_automation.binary_sensor import async_setup_entry
    elif platform_name == "switch":
        from custom_components.smart_cover_automation.switch import async_setup_entry
    else:
        raise ValueError(f"Unknown platform: {platform_name}")

    # Capture entities added to the platform
    captured_entities = []

    def mock_async_add_entities(new_entities, update_before_add=False):
        captured_entities.extend(new_entities)

    await async_setup_entry(hass_mock, cast(IntegrationConfigEntry, entry), mock_async_add_entities)
    return captured_entities


def create_options_flow_mock_entry(data: dict[str, Any], options: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock Home Assistant config entry for testing options flow.

    This consolidates the duplicate _mock_entry functions found in options flow tests
    and provides a standardized implementation.

    Args:
        data: Initial configuration data (typically covers list, initial settings)
        options: Optional runtime options that override data values

    Returns:
        Mock config entry with data and options attributes
    """
    entry = MagicMock()
    entry.data = data
    entry.options = options or {}

    # Create a mock hass object with a states attribute
    hass = MagicMock()
    hass.states = MagicMock()
    entry.hass = hass
    return entry


def create_mock_hass_with_weather_service() -> MagicMock:
    """Create a standard mock Home Assistant instance with weather service setup.

    Consolidates the duplicate hass setup pattern found across test files:
    - Creates MagicMock with spec=HomeAssistant
    - Sets up states and services mocks
    - Configures weather service with current temperature

    Returns:
        Mock Home Assistant instance ready for testing
    """
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()

    # Setup weather service mock with standard pattern
    hass.services.async_call = AsyncMock(side_effect=create_mock_weather_service())
    # Store reference to allow temperature override in tests
    hass._weather_service_mock = create_mock_weather_service()
    return hass


def setup_hass_with_weather_and_entities(
    temp: float = 25.0,
    cover_entities: list[MagicMock] | None = None,
    sun_entity: MagicMock | None = None,
    weather_entity: MagicMock | None = None,
) -> MagicMock:
    """Create complete hass mock with weather service and entity states.

    Consolidates the common pattern of setting up Home Assistant with
    weather service and various entity states for comprehensive testing.

    Args:
        temp: Weather temperature to return (default: 25.0)
        cover_entities: List of cover entities to mock (default: single standard cover)
        sun_entity: Sun entity mock (default: standard sun entity)
        weather_entity: Weather entity mock (default: standard weather entity)

    Returns:
        Fully configured Home Assistant mock
    """
    hass = create_mock_hass_with_weather_service()

    # Set weather temperature
    set_weather_forecast_temp(temp)

    # Setup entity states
    if cover_entities is None:
        cover_entities = [create_standard_cover_state()]

    if sun_entity is None:
        sun_entity = create_standard_sun_state()

    if weather_entity is None:
        weather_entity = create_standard_weather_state()

    # Create state getter that returns appropriate entities
    entity_states = {weather_entity.entity_id: weather_entity, sun_entity.entity_id: sun_entity}
    for cover in cover_entities:
        entity_states[cover.entity_id] = cover

    hass.states.get.side_effect = create_mock_state_getter(**entity_states)
    return hass


# Additional consolidated fixtures to eliminate common duplicate patterns


@pytest.fixture
def mock_basic_hass() -> MagicMock:
    """Create a basic mock Home Assistant instance.

    This fixture consolidates the duplicate `hass = MagicMock()` patterns found
    across multiple test files, providing a standardized basic mock with the
    most commonly used attributes configured.

    Returns:
        MagicMock: Basic Home Assistant mock instance with states, services, and config_entries
    """
    hass = MagicMock()
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.config_entries = MagicMock()
    return hass


@pytest.fixture
def mock_hass_with_spec() -> MagicMock:
    """Create a mock Home Assistant instance with proper HomeAssistant spec.

    This fixture consolidates the duplicate `hass = MagicMock(spec=HomeAssistant)` patterns
    found across multiple test files, particularly in integration lifecycle tests.

    Returns:
        MagicMock: Home Assistant mock instance with HomeAssistant spec and configured attributes
    """
    from homeassistant.core import HomeAssistant

    hass = MagicMock(spec=HomeAssistant)
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_reload = AsyncMock()
    hass.data = {}
    hass.services = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    hass.services.async_remove = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry_basic() -> MockConfigEntry:
    """Create a basic mock config entry with temperature configuration.

    This fixture consolidates the duplicate `MockConfigEntry(create_temperature_config())`
    patterns found across multiple test files, providing a standardized config entry
    for tests that need a simple temperature-based automation configuration.

    Returns:
        MockConfigEntry: Mock config entry with temperature automation setup
    """
    return MockConfigEntry(create_temperature_config())


@pytest.fixture
def mock_coordinator_basic(mock_basic_hass, mock_config_entry_basic) -> DataUpdateCoordinator:
    """Create a basic coordinator instance for testing.

    This fixture consolidates the duplicate coordinator creation patterns found
    across multiple test files, combining the basic hass and config entry fixtures
    for consistent test setup.

    Args:
        mock_basic_hass: Basic Home Assistant mock fixture
        mock_config_entry_basic: Basic config entry mock fixture

    Returns:
        DataUpdateCoordinator: Configured coordinator instance ready for testing
    """
    from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
    from custom_components.smart_cover_automation.data import IntegrationConfigEntry

    return DataUpdateCoordinator(mock_basic_hass, cast(IntegrationConfigEntry, mock_config_entry_basic))


@pytest.fixture
def mock_coordinator_with_empty_data(mock_coordinator_basic) -> DataUpdateCoordinator:
    """Create a coordinator with empty data for edge case testing.

    This fixture sets up a coordinator with empty data structure, which is
    useful for testing edge cases where coordinator data is missing or empty.

    Args:
        mock_coordinator_basic: Basic coordinator fixture

    Returns:
        DataUpdateCoordinator: Coordinator with empty data structure
    """
    mock_coordinator_basic.data = {}
    return mock_coordinator_basic
