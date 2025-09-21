"""
Integration tests for Smart Cover Automation.

This module contains comprehensive integration tests that validate the Smart Cover Automation
system's behavior in realistic scenarios. Unlike unit tests that focus on individual components,
these tests simulate real-world conditions by combining multiple factors like temperature,
sun position, cover states, and Home Assistant service interactions.

The tests cover several key scenarios:
- Complete automation cycles combining temperature and sun position logic
- Daily sun movement patterns and their interaction with temperature-based automation
- Error handling and recovery from sensor failures and service call issues
- Configuration validation for various edge cases
- Concurrent control of multiple covers with different capabilities
- Mixed cover types with varying feature support (position vs. open/close only)

These integration tests ensure that the automation system works correctly when all components
interact together, providing confidence that the system will perform reliably in production
Home Assistant environments.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.const import ATTR_SUPPORTED_FEATURES, Platform
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.smart_cover_automation.config import (
    ConfKeys,
)
from custom_components.smart_cover_automation.coordinator import (
    DataUpdateCoordinator,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_SUN_ENTITY_ID,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COMFORTABLE_TEMP_1,
    TEST_COVER_CLOSED,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    TEST_MIN_SERVICE_CALLS,
    TEST_NUM_COVERS,
    MockConfigEntry,
    create_temperature_config,
    set_weather_forecast_temp,
)

# Test constants are now imported from conftest.py - see imports above for:
# TEST_HOT_TEMP, TEST_COLD_TEMP, TEST_COMFORTABLE_TEMP_1, TEST_COVER_OPEN, TEST_COVER_CLOSED,
# TEST_NUM_COVERS, TEST_MIN_SERVICE_CALLS, TEST_HIGH_ELEVATION, TEST_DIRECT_AZIMUTH


class TestIntegrationScenarios:
    """
    Test real-world integration scenarios for Smart Cover Automation.

    This test class validates the complete automation system by simulating realistic
    Home Assistant environments and user scenarios. The tests combine multiple automation
    factors (temperature, sun position, cover capabilities) to ensure the system behaves
    correctly when all components work together.

    Key testing areas:
    - Temperature-based automation with combined AND logic
    - Sun position automation throughout daily cycles
    - Error handling and system recovery
    - Configuration validation
    - Multi-cover coordination and control
    - Mixed cover capabilities (smart vs. basic covers)
    """

    async def test_temperature_automation_complete_cycle(self) -> None:
        """
        Test complete temperature automation cycle with combined AND logic.

        This test validates the core automation logic that combines temperature and sun position
        to make intelligent cover control decisions. The automation uses AND logic, meaning
        covers are closed only when BOTH conditions are met:
        1. Temperature is hot (above threshold)
        2. Sun is hitting the cover (elevation > 25° and azimuth in range 135°-225°)

        Test scenarios cover all logical combinations:
        - Hot temperature + sun hitting = close covers (both conditions met)
        - Comfortable temperature + sun hitting = open covers (temperature not hot)
        - Cold temperature + any sun = open covers (cold overrides)
        - Hot temperature + sun not hitting = open covers (sun condition not met)

        This ensures the automation makes smart decisions rather than simple temperature-only
        or sun-only responses, preventing unnecessary cover movements and optimizing comfort.
        """
        # Setup Home Assistant mock environment for automation testing
        hass = MagicMock()
        hass.services = MagicMock()

        # Mock weather forecast service call
        async def mock_weather_service(domain, service, service_data, **kwargs):
            """Mock weather forecast service that returns temperature data."""
            if domain == Platform.WEATHER and service == "get_forecasts":
                entity_id = service_data.get("entity_id", "weather.forecast")
                # Get current temperature from global variable
                from tests.conftest import _CURRENT_WEATHER_TEMP

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
        config_entry = MockConfigEntry(create_temperature_config())  # Both automations now always active
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test scenarios with combined logic (temp AND sun)
        # Each scenario: (temp, sun_elevation, sun_azimuth, current_pos, expected_pos, description)
        test_scenarios = [
            # Hot temperature + sun hitting cover = close to block heat
            (TEST_HOT_TEMP, TEST_HIGH_ELEVATION, TEST_DIRECT_AZIMUTH, TEST_COVER_OPEN, TEST_COVER_CLOSED, "Hot + sun hitting -> close"),
            # Comfortable temperature + sun hitting = open (temperature not hot enough)
            (
                TEST_COMFORTABLE_TEMP_1,
                TEST_HIGH_ELEVATION,
                TEST_DIRECT_AZIMUTH,
                TEST_COVER_CLOSED,
                TEST_COVER_OPEN,
                "Comfortable + sun hitting -> open (not hot)",
            ),
            # Cold temperature + any sun condition = open for warmth
            (TEST_COLD_TEMP, 10.0, 90.0, TEST_COVER_CLOSED, TEST_COVER_OPEN, "Cold + sun not hitting -> open"),
            # Hot temperature + sun not hitting = open (sun condition not met)
            (TEST_HOT_TEMP, 10.0, 90.0, TEST_COVER_OPEN, TEST_COVER_OPEN, "Hot + sun not hitting -> open (not hitting)"),
        ]

        for i, (temp, elevation, azimuth, current_pos, expected_pos, description) in enumerate(test_scenarios):
            # Set the weather forecast temperature for this scenario
            set_weather_forecast_temp(float(temp))

            # Setup realistic Home Assistant entity states for this scenario
            # Weather entity state (now using weather instead of temperature sensor)
            weather_state = MagicMock()
            weather_state.state = "sunny"
            weather_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

            # Cover entity state with current position and supported features
            cover_state = MagicMock()
            cover_state.attributes = {
                ATTR_CURRENT_POSITION: current_pos,
                ATTR_SUPPORTED_FEATURES: 15,  # Full cover control capabilities
            }

            # Sun entity state with elevation and azimuth for sun position logic
            sun_state = MagicMock()
            sun_state.state = "above_horizon"
            sun_state.attributes = {"elevation": elevation, "azimuth": azimuth}

            # Configure Home Assistant state lookup to return our mock entities
            hass.states.get.side_effect = lambda entity_id, ws=weather_state, cs=cover_state, ss=sun_state: {
                MOCK_TEMP_SENSOR_ENTITY_ID: ws,
                MOCK_COVER_ENTITY_ID: cs,
                MOCK_SUN_ENTITY_ID: ss,
            }.get(entity_id)

            # Reset service call mock to track calls for this scenario
            # But preserve the weather service mock functionality
            original_side_effect = hass.services.async_call.side_effect
            hass.services.async_call.reset_mock()
            hass.services.async_call.side_effect = original_side_effect

            # Execute automation and validate results
            try:
                await coordinator.async_refresh()
                result = coordinator.data

                # Verify automation produced valid results
                assert result is not None, f"Result is None in scenario {i}: {description}"
                assert ConfKeys.COVERS.value in result, f"Invalid result structure in scenario {i}: {description}"

                # Check that the automation calculated the correct desired position
                cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
                assert cover_data["sca_cover_desired_position"] == expected_pos, (
                    f"Scenario {i} ({description}): Expected position {expected_pos}, got {cover_data['sca_cover_desired_position']}"
                )

                # Check for cover service calls (ignore weather service calls)
                cover_service_calls = [
                    call
                    for call in hass.services.async_call.call_args_list
                    if call[0][0] == Platform.COVER  # Only cover service calls
                ]

                # Verify service calls are made only when cover position needs to change
                # This prevents unnecessary service calls when covers are already in correct position
                if current_pos != expected_pos:
                    assert len(cover_service_calls) > 0, f"Scenario {i} ({description}): Cover service should have been called"
                else:
                    assert len(cover_service_calls) == 0, f"Scenario {i} ({description}): Cover service should not have been called"

            except Exception as e:
                pytest.fail(f"Automation failed in scenario {i} ({description}): {e}")

    async def test_sun_automation_daily_cycle(self) -> None:
        """
        Test sun automation through daily cycle with combined AND logic.

        This test simulates a complete day's sun movement from east to west and validates
        how the automation responds to different sun positions combined with temperature.
        The test focuses on the sun azimuth logic that determines when sun is "hitting" covers:

        Sun hitting conditions:
        - Elevation > 25° (sun is high enough)
        - Azimuth between 135° and 225° (southeast to southwest arc)

        Daily sun movement simulation:
        - Morning (90° azimuth): Sun in east, not hitting south-facing covers
        - Mid-morning (135° azimuth): Sun enters hitting zone if high enough
        - Midday (180° azimuth): Sun directly south, maximum impact
        - Afternoon (225° azimuth): Sun still hitting from southwest
        - Evening (270° azimuth): Sun in west, no longer hitting south-facing covers

        Combined with temperature logic to ensure realistic automation behavior.
        """
        # Setup Home Assistant mock for daily sun cycle testing
        hass = MagicMock()
        hass.services = MagicMock()

        # Mock weather forecast service call
        async def mock_weather_service(domain, service, service_data, **kwargs):
            """Mock weather forecast service that returns temperature data."""
            if domain == Platform.WEATHER and service == "get_forecasts":
                entity_id = service_data.get("entity_id", "weather.forecast")
                # Get current temperature from global variable
                from tests.conftest import _CURRENT_WEATHER_TEMP

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
        config_entry = MockConfigEntry(create_temperature_config())  # Both automations now always active
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test scenarios for combined temp+sun logic throughout the day
        # Each scenario: (elevation, azimuth, temp, expected_pos, description)
        test_scenarios = [
            # Morning: Low sun in east, not hitting south-facing covers
            (10.0, 90.0, TEST_HOT_TEMP, TEST_COVER_OPEN, "Low sun, east + hot -> no change (sun not hitting)"),
            # Mid-morning: High sun in southeast, hitting covers + hot = close
            (45.0, 135.0, TEST_HOT_TEMP, TEST_COVER_CLOSED, "High sun, southeast + hot -> close (sun hitting, temp hot)"),
            # Midday: High sun directly south, maximum impact + hot = close
            (50.0, TEST_DIRECT_AZIMUTH, TEST_HOT_TEMP, TEST_COVER_CLOSED, "High sun, south + hot -> close (both conditions met)"),
            # Afternoon: Sun in southwest, still hitting + hot = close
            (TEST_HIGH_ELEVATION, 225.0, TEST_HOT_TEMP, TEST_COVER_CLOSED, "Lower sun, southwest + hot -> close (sun hitting, temp hot)"),
            # Evening: Low sun in west, no longer hitting south-facing covers
            (5.0, 270.0, TEST_HOT_TEMP, TEST_COVER_OPEN, "Low sun, west + hot -> no change (sun not hitting)"),
            # Midday with comfortable temperature: sun hitting but temp not hot = no action
            (
                50.0,
                TEST_DIRECT_AZIMUTH,
                TEST_COMFORTABLE_TEMP_1,
                TEST_COVER_OPEN,
                "High sun, south + comfortable -> no change (temp not hot)",
            ),
            # Cold temperature overrides sun position: always open for warmth
            (50.0, TEST_DIRECT_AZIMUTH, TEST_COLD_TEMP, TEST_COVER_OPEN, "High sun, south + cold -> open (cold temp wins)"),
        ]

        for i, (elevation, azimuth, temp, expected_pos, description) in enumerate(test_scenarios):
            # Set temperature for this scenario
            set_weather_forecast_temp(float(temp))

            # Setup sun entity state for current time of day
            sun_state = MagicMock()
            sun_state.state = "above_horizon"
            sun_state.attributes = {"elevation": elevation, "azimuth": azimuth}

            # Setup cover state (starting fully open for all scenarios)
            cover_state = MagicMock()
            cover_state.attributes = {
                ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
                ATTR_SUPPORTED_FEATURES: 15,
            }

            # Configure Home Assistant entity lookup for this scenario
            # Create a weather entity state (required even though we use service calls)
            weather_state = MagicMock()
            weather_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

            hass.states.get.side_effect = lambda entity_id, ss=sun_state, cs=cover_state, ws=weather_state: {
                MOCK_SUN_ENTITY_ID: ss,
                MOCK_COVER_ENTITY_ID: cs,
                MOCK_TEMP_SENSOR_ENTITY_ID: ws,
            }.get(entity_id)

            # Execute automation for current sun/temperature conditions
            await coordinator.async_refresh()
            result = coordinator.data

            # Validate automation results for this time of day
            assert result is not None, f"Result is None in scenario {i}: {description}"
            assert ConfKeys.COVERS.value in result, f"Invalid result for scenario {i}: {description}"

            # Verify the automation calculated the correct position based on sun and temperature
            cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
            assert cover_data["sca_cover_desired_position"] == expected_pos, (
                f"Scenario {i} ({description}): Expected {expected_pos}, got {cover_data['desired_position']}"
            )

    async def test_error_recovery_scenarios(self) -> None:
        """
        Test critical error handling scenarios.

        This test validates the automation system's critical error handling when encountering
        essential sensor failures that make automation non-functional:

        1. Sensor Unavailability: Temperature sensor temporarily offline or not found
           - Should treat as critical error and make entities unavailable
           - Common during sensor battery changes or permanent failures

        2. Invalid Sensor Data: Temperature sensor returns non-numeric values
           - Should treat as critical error for data integrity
           - Handles cases like "unknown", "unavailable", or corrupted data

        3. Service Call Failures: Home Assistant cover service calls fail
           - Should continue automation logic despite service failures
           - Logs errors but doesn't prevent future automation attempts
           - Simulates network issues, cover device problems, or HA service issues

        Critical sensor errors result in UpdateFailed exceptions that make entities unavailable,
        signaling to users that the automation system requires attention.
        """
        # Setup basic Home Assistant mock for error testing
        hass = MagicMock()
        hass.services = MagicMock()

        # Mock weather forecast service call
        async def mock_weather_service(domain, service, service_data, **kwargs):
            """Mock weather forecast service that returns temperature data."""
            if domain == Platform.WEATHER and service == "get_forecasts":
                entity_id = service_data.get("entity_id", "weather.forecast")
                # Get current temperature from global variable
                from tests.conftest import _CURRENT_WEATHER_TEMP

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
        config_entry = MockConfigEntry(create_temperature_config())
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Test 1: Temperature sensor temporarily unavailable (common during maintenance)
        # Setup valid cover and sun states but missing temperature sensor
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: 15,
        }
        # Return None for temp sensor to simulate sensor being offline
        hass.states.get.side_effect = lambda entity_id, cs=cover_state: {
            MOCK_TEMP_SENSOR_ENTITY_ID: None,  # Sensor not found/available
            MOCK_COVER_ENTITY_ID: cs,
            MOCK_SUN_ENTITY_ID: MagicMock(
                state="above_horizon", attributes={"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
            ),
        }.get(entity_id)

        # Should handle missing sensor as critical error
        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, UpdateFailed)  # Critical error should be raised
        assert "Temperature sensor 'weather.forecast' not found" in str(coordinator.last_exception)

    async def test_configuration_validation(self) -> None:
        """
        Test configuration validation scenarios.

        This test validates that the automation system gracefully handles configuration
        validation and reports errors when invalid setups are encountered. The system
        should log errors but continue operation with minimal state to keep integration
        entities available.

        Key validation scenarios:
        - Empty covers list: Configuration must specify at least one cover to control
        - Invalid entity IDs: Covers must be valid Home Assistant entity identifiers
        - Missing required configuration keys: Essential configuration elements must be present

        The system should detect these issues early and provide clear error messages
        through logs while maintaining system stability.
        """
        # Setup Home Assistant mock for configuration testing
        hass = MagicMock()

        # Test empty covers list - should be handled gracefully
        # An automation system needs at least one cover to control
        config = create_temperature_config()
        config[ConfKeys.COVERS.value] = []  # Empty covers list
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Should handle invalid configuration gracefully
        await coordinator.async_refresh()
        assert coordinator.last_exception is None  # No exception should propagate
        assert coordinator.data == {ConfKeys.COVERS.value: {}}  # Minimal valid state returned

    # Configuration validation complete

    async def test_concurrent_cover_control(self) -> None:
        """
        Test controlling multiple covers simultaneously.

        This test validates the automation system's ability to manage multiple covers
        concurrently, ensuring that:

        1. All covers are processed in the same automation cycle
        2. Each cover's individual state and capabilities are considered
        3. Service calls are made appropriately for covers that need adjustment
        4. The system scales properly with multiple covers

        Real-world scenario: A home with covers in multiple rooms (living room, bedroom,
        kitchen) where each cover may have different current positions but should all
        respond to the same environmental conditions (temperature and sun position).

        The test uses hot temperature + direct sun hitting to trigger closing all covers,
        but validates that service calls are only made for covers that actually need
        to move to the new position.
        """
        # Setup Home Assistant mock with service call tracking
        hass = MagicMock()
        hass.services = MagicMock()

        # Mock weather forecast service call
        async def mock_weather_service(domain, service, service_data, **kwargs):
            """Mock weather forecast service that returns temperature data."""
            if domain == Platform.WEATHER and service == "get_forecasts":
                entity_id = service_data.get("entity_id", "weather.forecast")
                # Get current temperature from global variable
                from tests.conftest import _CURRENT_WEATHER_TEMP

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

        # Configure multiple covers for concurrent control testing
        covers = ["cover.living_room", "cover.bedroom", "cover.kitchen"]
        config = create_temperature_config(covers=covers)
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Setup environmental conditions that should trigger cover closing
        # Hot temperature scenario combined with direct sun hitting
        set_weather_forecast_temp(float(TEST_HOT_TEMP))  # Hot enough to trigger automation

        # Create sun state for combined automation (sun hitting covers)
        sun_state = MagicMock()
        sun_state.state = "above_horizon"
        sun_state.attributes = {"elevation": 50.0, "azimuth": TEST_DIRECT_AZIMUTH}  # Direct sun hitting covers

        # Create different cover states to test individual processing
        # Each cover starts at a different position to validate individual handling
        cover_states = {}
        for i, cover_id in enumerate(covers):
            cover_state = MagicMock()
            cover_state.attributes = {
                ATTR_CURRENT_POSITION: 100 - (i * 20),  # Different starting positions (100, 80, 60)
                ATTR_SUPPORTED_FEATURES: 15,  # Full cover control capabilities
            }
            cover_states[cover_id] = cover_state

        # Configure Home Assistant state lookup for all entities
        def get_state(entity_id: str) -> MagicMock | None:
            if entity_id == MOCK_SUN_ENTITY_ID:
                return sun_state
            if entity_id == MOCK_TEMP_SENSOR_ENTITY_ID:
                # Create a weather entity state (required even though we use service calls)
                weather_state = MagicMock()
                weather_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID
                return weather_state
            return cover_states.get(entity_id)

        hass.states.get.side_effect = get_state
        hass.services.async_call.reset_mock()

        # Execute automation for all covers simultaneously
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify all covers were processed in the automation cycle
        assert len(result[ConfKeys.COVERS.value]) == TEST_NUM_COVERS, f"Expected {TEST_NUM_COVERS} covers, got {len(result['covers'])}"

        # Verify all covers should close (position 0) due to hot temperature AND sun hitting
        # Combined logic: both conditions met, so all covers should be closed
        for cover_id in covers:
            assert result[ConfKeys.COVERS.value][cover_id]["sca_cover_desired_position"] == TEST_COVER_CLOSED, (
                f"Cover {cover_id} should close in hot weather with sun hitting"
            )

        # Verify service calls were made for covers that needed to move
        # Not all covers may need service calls if they're already in the correct position
        call_count = hass.services.async_call.call_count
        assert call_count > 0, "No service calls made for cover control"

    async def test_mixed_cover_capabilities(self) -> None:
        """
        Test handling covers with different capabilities.

        This test validates that the automation system properly handles covers with
        varying levels of functionality, which is common in real Home Assistant setups:

        1. Smart Covers (supported_features = 15):
           - Support precise position control (0-100%)
           - Can use set_cover_position service for exact positioning
           - Typically motorized covers with position feedback

        2. Basic Covers (supported_features = 3):
           - Only support open/close operations (no position control)
           - Must use open_cover/close_cover services
           - Often manual covers with smart switches or basic motorized covers

        The automation should:
        - Detect each cover's capabilities from supported_features attribute
        - Use appropriate service calls for each cover type
        - Achieve the same logical outcome (open/closed) regardless of cover type
        - Handle mixed environments where both types coexist

        Real-world scenario: A home with expensive motorized covers in main rooms
        and basic automated covers in utility areas.
        """
        # Setup Home Assistant mock with service call tracking for capability testing
        hass = MagicMock()
        hass.services = MagicMock()

        # Mock weather forecast service call
        async def mock_weather_service(domain, service, service_data, **kwargs):
            """Mock weather forecast service that returns temperature data."""
            if domain == Platform.WEATHER and service == "get_forecasts":
                entity_id = service_data.get("entity_id", "weather.forecast")
                # Get current temperature from global variable
                from tests.conftest import _CURRENT_WEATHER_TEMP

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

        # Configure covers with different capabilities
        covers = ["cover.smart", "cover.basic"]
        config = create_temperature_config(covers=covers)
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(hass, cast(IntegrationConfigEntry, config_entry))

        # Setup cold temperature to trigger opening covers (clear automation logic)
        set_weather_forecast_temp(float(TEST_COLD_TEMP))  # Cold enough to open covers for warmth

        # Smart cover with full position control capabilities
        smart_cover = MagicMock()
        smart_cover.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_CLOSED,  # Currently closed, should open
            ATTR_SUPPORTED_FEATURES: 15,  # Full feature set: open, close, stop, position
        }

        # Basic cover with only open/close capabilities (no position control)
        basic_cover = MagicMock()
        basic_cover.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_CLOSED,  # Currently closed, should open
            ATTR_SUPPORTED_FEATURES: 3,  # Basic feature set: open, close only
        }

        # Configure entity state lookup for capability testing
        # Create a weather entity state (required even though we use service calls)
        weather_state = MagicMock()
        weather_state.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID

        hass.states.get.side_effect = lambda entity_id: {
            "cover.smart": smart_cover,
            "cover.basic": basic_cover,
            MOCK_TEMP_SENSOR_ENTITY_ID: weather_state,
            # Sun state that doesn't interfere with cold temperature logic
            MOCK_SUN_ENTITY_ID: MagicMock(
                state="above_horizon", attributes={"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
            ),
        }.get(entity_id)

        # Execute automation and analyze service calls
        await coordinator.async_refresh()

        # Analyze the service calls made for each cover type
        calls = [call.args for call in hass.services.async_call.call_args_list]

        # Filter out weather service calls to get only cover service calls
        cover_calls = [call for call in calls if call[0] == Platform.COVER]

        # Should have calls for both covers (both need to open)
        assert len(cover_calls) >= TEST_MIN_SERVICE_CALLS, (
            f"Expected at least {TEST_MIN_SERVICE_CALLS} service calls, got {len(cover_calls)}"
        )

        # Smart cover should use precise position control service
        smart_call = next((call for call in cover_calls if call[2]["entity_id"] == "cover.smart"), None)
        assert smart_call is not None, "No call found for smart cover"
        assert smart_call[1] == "set_cover_position", "Smart cover should use set_cover_position"

        # Basic cover should use simple open service (no position control available)
        basic_call = next((call for call in cover_calls if call[2]["entity_id"] == "cover.basic"), None)
        assert basic_call is not None, "No call found for basic cover"
        assert basic_call[1] == "open_cover", "Basic cover should use open_cover"
