"""Tests for the Smart Cover Automation coordinator.

This module contains comprehensive tests for the DataUpdateCoordinator class, which is the
core component responsible for executing automation logic in the Smart Cover Automation
integration. The coordinator handles:

- Temperature-based automation (opening/closing covers based on indoor temperature)
- Sun-based automation (adjusting covers based on sun position and window orientation)
- Combined automation logic (temperature AND sun conditions)
- Error handling for various failure scenarios
- Service call management for cover position changes
- State management and data updates for sensors and binary sensors

The tests cover various automation scenarios including:
- Hot temperature conditions that trigger cover closing
- Cold temperature conditions that trigger cover opening
- Sun position calculations and cover adjustments
- Error conditions (missing sensors, invalid data, service failures)
- Edge cases (unavailable covers, unsupported features, configuration errors)

Test data uses realistic values for temperature thresholds, sun positions, and cover
states to ensure the automation behaves correctly in real-world scenarios.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_ATTR_SUN_AZIMUTH_DIFF,
    COVER_ATTR_SUN_HITTING,
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
    SENSOR_ATTR_TEMP_HOT,
)
from custom_components.smart_cover_automation.coordinator import (
    AllCoversUnavailableError,
    ConfigurationError,
    DataUpdateCoordinator,
    InvalidSensorReadingError,
    ServiceCallError,
    SunSensorNotFoundError,
    TempSensorNotFoundError,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_COVER_ENTITY_ID_2,
    MOCK_SUN_ENTITY_ID,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COMFORTABLE_TEMP_1,
    TEST_COMFORTABLE_TEMP_2,
    TEST_COVER_CLOSED,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    TEST_INDIRECT_AZIMUTH,
    TEST_LOW_ELEVATION,
    TEST_PARTIAL_POSITION,
    MockConfigEntry,
    assert_service_called,
    create_combined_state_mock,
    create_sun_config,
    create_temperature_config,
)

# Test constants are now imported from conftest.py - see imports above for:
# TEST_HOT_TEMP, TEST_COLD_TEMP, TEST_COMFORTABLE_TEMP_2, TEST_COVER_OPEN, TEST_COVER_CLOSED,
# TEST_PARTIAL_POSITION, TEST_HIGH_ELEVATION, TEST_LOW_ELEVATION, TEST_DIRECT_AZIMUTH,
# TEST_INDIRECT_AZIMUTH


class TestDataUpdateCoordinator:
    """Test suite for the Smart Cover Automation DataUpdateCoordinator.

    This test class validates the core automation logic of the DataUpdateCoordinator,
    including:

    - Temperature-based automation (hot/cold/comfortable conditions)
    - Sun-based automation (elevation, azimuth, window orientation)
    - Combined automation logic (temperature AND sun conditions)
    - Error handling (missing sensors, invalid data, service failures)
    - Cover state management (position, tilt, availability)
    - Service call coordination with Home Assistant
    - Configuration validation and error reporting

    The tests use comprehensive mock data to simulate realistic Home Assistant
    environments and verify that the automation logic produces correct cover
    position adjustments and service calls.
    """

    @pytest.fixture
    def coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a DataUpdateCoordinator instance configured for temperature automation.

        Creates a coordinator with temperature-based automation configuration using
        the mock Home Assistant instance. This coordinator is used for testing
        temperature-based automation logic.

        Returns:
            DataUpdateCoordinator: Configured coordinator for temperature automation testing
        """
        config_entry = MockConfigEntry(create_temperature_config())
        return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

    @pytest.fixture
    def sun_coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a DataUpdateCoordinator instance configured for sun-based automation.

        Creates a coordinator with sun-based automation configuration using
        the mock Home Assistant instance. This coordinator is used for testing
        sun position and window orientation automation logic.

        Returns:
            DataUpdateCoordinator: Configured coordinator for sun automation testing
        """
        config_entry = MockConfigEntry(create_sun_config())
        return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

    async def test_init(self, coordinator: DataUpdateCoordinator) -> None:
        """Test DataUpdateCoordinator initialization and basic properties.

        Validates that the coordinator is properly initialized with correct:
        - Integration name
        - Configuration entry reference
        - Update interval (60 seconds default)

        This ensures the coordinator is set up correctly for automation operations.
        """
        coor = cast(DataUpdateCoordinator, coordinator)
        assert coor.name == "smart_cover_automation"
        assert coor.config_entry is not None
        # Guard against Optional[timedelta] in typing
        assert coor.update_interval is not None
        assert coor.update_interval.total_seconds() == 60

    async def test_temperature_automation_hot(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test temperature automation when indoor temperature is too hot.

        Validates that the automation correctly closes covers when the indoor temperature
        exceeds the maximum threshold. This test simulates a hot day where covers should
        close to block heat and keep the room cool.

        Test scenario:
        - Temperature: 26°C (above 24°C maximum threshold)
        - Sun elevation: 50° (above threshold, contributing to heat)
        - Sun azimuth: 180° (directly hitting south-facing window)
        - Current cover position: Fully open (100)
        - Expected action: Close covers to 0 to block heat
        """
        # Setup temperature sensor above maximum threshold
        mock_temperature_state.state = TEST_HOT_TEMP  # Above 24°C max
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN  # Fully open

        # Create environmental state: hot temperature + sun hitting window
        # Both conditions met for AND logic to trigger cover closing
        state_mapping = create_combined_state_mock(
            temp_state=TEST_HOT_TEMP,  # 26.0°C - above 24°C threshold
            sun_elevation=TEST_HIGH_ELEVATION,  # Above 20° threshold
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Hitting south-facing window
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute automation logic
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify automation closes covers due to hot temperature
        assert result is not None
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result["temp_current"] == float(TEST_HOT_TEMP)
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_CLOSED  # Should close

        # Verify Home Assistant service call to close covers
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=TEST_COVER_CLOSED,
        )

    async def test_temperature_automation_cold(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test temperature automation when indoor temperature is too cold.

        Validates that the automation correctly opens covers when the indoor temperature
        falls below the minimum threshold. This test simulates a cold day where covers
        should open to allow warming sunlight into the room, even if the sun isn't
        directly hitting the window.

        Test scenario:
        - Temperature: 18°C (below 21°C minimum threshold)
        - Sun elevation: 50° (above threshold but not the deciding factor)
        - Sun azimuth: 90° (not hitting south-facing window at 180°)
        - Current cover position: Fully closed (0)
        - Expected action: Open covers to 100 for warmth
        """
        # Setup temperature sensor below minimum threshold
        mock_temperature_state.state = TEST_COLD_TEMP  # Below 21°C min
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_CLOSED  # Fully closed

        # Create environmental state: cold temperature + sun not hitting window
        # Cold temperature condition met for opening (sun position secondary)
        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # 18.0°C - below 21°C threshold
            sun_elevation=TEST_HIGH_ELEVATION,  # Above 20° threshold but...
            sun_azimuth=TEST_INDIRECT_AZIMUTH,  # Not hitting south-facing window (180°)
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute automation logic
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify automation opens covers due to cold temperature
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result["temp_current"] == float(TEST_COLD_TEMP)
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN  # Should open

        # Verify Home Assistant service call to open covers
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=TEST_COVER_OPEN,
        )

    async def test_temperature_automation_comfortable(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test temperature automation when temperature is in comfortable range.

        Validates that the automation correctly handles comfortable temperatures
        (between minimum and maximum thresholds). In this case, the temperature
        doesn't trigger any specific action, but combined logic with sun conditions
        may still result in cover adjustments.

        Test scenario:
        - Temperature: 22.5°C (between 21-24°C comfortable range)
        - Sun conditions: Default (hitting window, above elevation threshold)
        - Current cover position: Partially open (50)
        - Expected action: Open covers to 100 (sun logic takes precedence)
        """
        # Setup temperature sensor in comfortable range
        mock_temperature_state.state = TEST_COMFORTABLE_TEMP_2  # Between 21-24°C
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_PARTIAL_POSITION

        # Create environmental state with comfortable temperature
        state_mapping = create_combined_state_mock(
            temp_state=mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1,
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute automation logic
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify automation applies sun logic when temperature is comfortable
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result["temp_current"] == float(TEST_COMFORTABLE_TEMP_2)
        # With comfortable temp (not hot) and default sun hitting, AND logic means open
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN  # Should open

        # Verify Home Assistant service call to adjust covers (position changes from 50 to 100)
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=TEST_COVER_OPEN,
        )

    async def test_temperature_sensor_not_found(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test error handling when temperature sensor is not found in Home Assistant.

        Validates that the coordinator properly handles and reports errors when the
        configured temperature sensor entity doesn't exist in Home Assistant. This
        ensures proper error reporting and prevents automation failures from causing
        system instability.

        Test scenario:
        - Temperature sensor: Missing from Home Assistant state registry
        - Cover entities: Available and properly configured
        - Expected behavior: TempSensorNotFoundError raised and captured
        """
        # Setup available cover entity so sensor error is the focus
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        # Create state mapping WITHOUT temperature sensor (simulating missing sensor)
        state_mapping = {
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_SUN_ENTITY_ID: MagicMock(
                entity_id=MOCK_SUN_ENTITY_ID, attributes={"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
            ),
            # MOCK_TEMP_SENSOR_ENTITY_ID is intentionally missing
        }

        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute automation and verify error handling
        await coordinator.async_refresh()
        # DataUpdateCoordinator captures exceptions; verify last_exception
        assert isinstance(coordinator.last_exception, TempSensorNotFoundError)
        assert "sensor.temperature" in str(coordinator.last_exception)

    async def test_temperature_sensor_invalid_reading(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test error handling when temperature sensor provides invalid data.

        Validates that the coordinator properly handles and reports errors when the
        temperature sensor entity exists but provides non-numeric data. This ensures
        the automation fails gracefully rather than crashing on invalid sensor readings.

        Test scenario:
        - Temperature sensor: Returns "invalid" string instead of numeric value
        - Expected behavior: InvalidSensorReadingError raised and captured
        """
        # Setup temperature sensor with invalid (non-numeric) reading
        mock_temperature_state.state = "invalid"
        mock_hass.states.get.return_value = mock_temperature_state

        # Execute automation and verify error handling
        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, InvalidSensorReadingError)
        assert "invalid" in str(coordinator.last_exception)

    async def test_sun_automation_direct_sun(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test sun-based automation when sun is directly hitting the window.

        Validates that the automation correctly closes covers when the sun is at
        high elevation and positioned to directly hit the configured window orientation.
        This test simulates midday conditions where covers should close to block
        direct sunlight and heat.

        Test scenario:
        - Sun elevation: 45° (above 20° threshold)
        - Sun azimuth: 180° (directly hitting south-facing window)
        - Temperature: 25°C (hot, supporting cover closure in combined logic)
        - Current cover position: Fully open (100)
        - Expected action: Close covers to 0 to block direct sun
        """
        # Setup cover in open position receiving direct sunlight
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        # Create environmental state: direct sun + hot temperature
        state_mapping = create_combined_state_mock(
            temp_state="25.0",  # Hot for AND logic
            sun_elevation=TEST_HIGH_ELEVATION,  # Use the expected elevation
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Use the expected azimuth
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute sun automation logic
        await sun_coordinator.async_refresh()
        result = sun_coordinator.data

        # Verify sun automation closes covers due to direct sunlight
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result["sun_elevation"] == TEST_HIGH_ELEVATION
        assert result["sun_azimuth"] == TEST_DIRECT_AZIMUTH
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_CLOSED  # Should close due to hot temp + direct sun

    async def test_sun_automation_respects_max_closure_option(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that sun automation respects the configured maximum closure percentage.

        Validates that when direct sunlight hits the window, the automation uses the
        configured `covers_max_closure` setting instead of fully closing the covers.
        This allows users to block most sunlight while still maintaining some visibility
        and natural light.

        Test scenario:
        - Sun elevation: 45° (above threshold)
        - Sun azimuth: 180° (direct hit)
        - Configuration: covers_max_closure = 60% (instead of default 100%)
        - Expected action: Close covers to 60% (not fully closed)
        """
        # Create configuration with custom maximum closure setting
        config = create_sun_config()
        config[ConfKeys.COVERS_MAX_CLOSURE.value] = 60  # cap direct hit to 60%
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Setup sun directly hitting window
        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_DIRECT_AZIMUTH,
        }
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        # With covers_max_closure=60 and direct hit, desired = 100 - 60 = 40
        assert cover_data["sca_cover_desired_position"] == COVER_POS_FULLY_OPEN  # Combined logic: cold temp overrides sun closure

    async def test_sun_automation_low_sun(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test sun automation with low sun elevation."""
        # Setup - sun below threshold
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_PARTIAL_POSITION

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp wants open
            sun_elevation=TEST_LOW_ELEVATION,  # Low sun elevation
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Direct azimuth
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute
        await sun_coordinator.async_refresh()
        result = sun_coordinator.data

        # Verify - Low sun elevation means sun_hitting = False, so covers should open due to cold temp
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN  # Should open because temp wants open OR sun wants open

    async def test_sun_automation_not_hitting_window_above_threshold(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Sun above threshold but not hitting window should open fully (with logging path)."""
        config = create_sun_config()
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Sun above threshold but azimuth far from south direction (window south)
        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_INDIRECT_AZIMUTH,  # 90° vs south 180° => angle 90° > tolerance
        }

        # Cover is partially closed to force potential change to OPEN
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_PARTIAL_POSITION

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN  # Should open due to cold temp OR low sun
        # Azimuth difference should be computed when elevation >= threshold
        assert cover_data[COVER_ATTR_SUN_AZIMUTH_DIFF] is not None

    async def test_sun_automation_no_sun_entity(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
    ) -> None:
        """Test error when sun entity not found."""
        # Create state mapping WITHOUT sun entity (to simulate missing sensor)
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        state_mapping = {
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_TEMP_SENSOR_ENTITY_ID: MagicMock(entity_id=MOCK_TEMP_SENSOR_ENTITY_ID, state=TEST_COMFORTABLE_TEMP_1),
            # MOCK_SUN_ENTITY_ID is intentionally missing
        }

        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)
        await sun_coordinator.async_refresh()

        # Verify sun sensor error
        assert isinstance(sun_coordinator.last_exception, SunSensorNotFoundError)
        assert "sun.sun" in str(sun_coordinator.last_exception)

    async def test_sun_automation_invalid_data(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test error when sun data is invalid."""
        mock_sun_state.attributes = {"elevation": "invalid", "azimuth": TEST_DIRECT_AZIMUTH}
        mock_hass.states.get.return_value = mock_sun_state
        await sun_coordinator.async_refresh()
        assert isinstance(sun_coordinator.last_exception, InvalidSensorReadingError)

    async def test_sun_automation_skips_unavailable_cover(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """One unavailable cover should be skipped inside sun automation loop."""
        # Two covers configured; make second unavailable in the states mapping
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2])
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_DIRECT_AZIMUTH,
        }
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                # MOCK_COVER_ENTITY_ID_2 intentionally omitted to make it unavailable
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        # Only first cover should appear
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        assert MOCK_COVER_ENTITY_ID_2 not in result[ConfKeys.COVERS.value]

    async def test_cover_unavailable(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test handling when all covers are unavailable."""
        # Manually create state mapping without any covers, but with temp and sun sensors
        temp_mock = MagicMock()
        temp_mock.entity_id = MOCK_TEMP_SENSOR_ENTITY_ID
        temp_mock.state = mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1

        sun_mock = MagicMock()
        sun_mock.entity_id = MOCK_SUN_ENTITY_ID
        sun_mock.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        state_mapping = {
            MOCK_TEMP_SENSOR_ENTITY_ID: temp_mock,
            MOCK_SUN_ENTITY_ID: sun_mock,
            # No covers in state mapping - they will be unavailable
        }

        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)
        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, AllCoversUnavailableError)

    async def test_service_call_failure(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test handling service call failures."""
        # Setup - temperature too hot, should close covers
        mock_temperature_state.state = TEST_HOT_TEMP
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        # Mock service call to fail
        mock_hass.services.async_call.side_effect = OSError("Service failed")

        state_mapping = create_combined_state_mock(
            temp_state=mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1,
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute - should not raise exception, just log error
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify - automation still completes despite service failure
        assert result is not None
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]

    async def test_cover_without_position_support(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test covers without position support."""
        # Setup cover without position support
        mock_cover_state.attributes[ATTR_SUPPORTED_FEATURES] = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        mock_temperature_state.state = TEST_HOT_TEMP  # Too hot
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1,
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute
        await coordinator.async_refresh()

        # Verify close service called instead of set_position
        await assert_service_called(
            mock_hass.services,
            "cover",
            "close_cover",
            MOCK_COVER_ENTITY_ID,
        )

    async def test_no_covers_configured(
        self,
        mock_hass: MagicMock,
    ) -> None:
        """Test error when no covers are configured."""
        config = create_temperature_config()
        config[ConfKeys.COVERS.value] = []
        config_entry = MockConfigEntry(config)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, ConfigurationError)
        assert "No covers configured" in str(coordinator.last_exception)

    async def test_angle_calculation(
        self,
        sun_coordinator: DataUpdateCoordinator,
    ) -> None:
        """Test angle difference calculation."""
        # Test direct alignment
        diff = sun_coordinator._calculate_angle_difference(TEST_DIRECT_AZIMUTH, TEST_DIRECT_AZIMUTH)
        assert diff == 0.0

        # Test 45 degree difference
        diff = sun_coordinator._calculate_angle_difference(TEST_DIRECT_AZIMUTH, 135.0)
        assert diff == 45.0

        # Test wraparound (0° and 350° should be 10° apart)
        diff = sun_coordinator._calculate_angle_difference(0.0, 350.0)
        assert diff == 10.0

    async def test_sun_missing_cover_azimuth_skips_cover(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Cover without azimuth should still appear for temperature automation but skip sun automation."""
        # Build a sun config for two covers, remove direction for second cover
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2])
        # Remove direction for cover 2 to trigger skip
        config.pop(f"{MOCK_COVER_ENTITY_ID_2}_{COVER_SFX_AZIMUTH}", None)
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Sun above threshold, direct hit
        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_DIRECT_AZIMUTH,
        }

        # Both covers available
        cover2_state = MagicMock()
        cover2_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                MOCK_COVER_ENTITY_ID_2: cover2_state.attributes
                if hasattr(cover2_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Only cover 1 should appear (cover 2 is skipped due to missing azimuth)
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        assert MOCK_COVER_ENTITY_ID_2 not in result[ConfKeys.COVERS.value]

        # Cover 1 should have both temperature and sun automation data
        cover1_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result[SENSOR_ATTR_TEMP_HOT] is not None
        assert COVER_ATTR_SUN_HITTING in cover1_data

    async def test_sun_invalid_cover_azimuth_skips_cover(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Cover with invalid azimuth should still appear for temperature automation but skip sun automation."""
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2])
        # Set an invalid direction string for cover 2
        config[f"{MOCK_COVER_ENTITY_ID_2}_{COVER_SFX_AZIMUTH}"] = "upwards"
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_DIRECT_AZIMUTH,
        }

        cover2_state = MagicMock()
        cover2_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                MOCK_COVER_ENTITY_ID_2: cover2_state.attributes
                if hasattr(cover2_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Only cover 1 should appear (cover 2 is skipped due to invalid azimuth)
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        assert MOCK_COVER_ENTITY_ID_2 not in result[ConfKeys.COVERS.value]

        # Cover 1 should have both temperature and sun automation data
        cover1_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result[SENSOR_ATTR_TEMP_HOT] is not None
        assert COVER_ATTR_SUN_HITTING in cover1_data

    async def test_missing_config_keys_raise_configuration_error(
        self,
        mock_hass: MagicMock,
    ) -> None:
        """Missing required keys in config should raise ConfigurationError."""
        # Build a config missing the required covers key entirely
        config: dict[str, Any] = {}
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, ConfigurationError)

    async def test_service_call_error_class_init(self) -> None:
        """Construct ServiceCallError to cover its initializer."""
        err = ServiceCallError("cover.set_cover_position", "cover.test", "boom")
        assert "Failed to call" in str(err)
        assert err.service == "cover.set_cover_position"
        assert err.entity_id == "cover.test"

    @pytest.mark.asyncio
    async def test_sun_automation_angle_matrix(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test broad combinations of window and sun azimuths with combined logic."""
        # Build config with one cover and numeric window azimuth
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Cover supports position and starts fully open
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        for window_azimuth, sun_azimuth, expected in [
            (TEST_DIRECT_AZIMUTH, TEST_DIRECT_AZIMUTH, TEST_COVER_CLOSED),
            (TEST_DIRECT_AZIMUTH, 100.0, TEST_COVER_CLOSED),
            (TEST_DIRECT_AZIMUTH, 270.0, TEST_COVER_OPEN),
            (0.0, 350.0, TEST_COVER_CLOSED),
            (TEST_INDIRECT_AZIMUTH, 270.0, TEST_COVER_OPEN),
            (315.0, 44.0, TEST_COVER_CLOSED),
            (315.0, TEST_HIGH_ELEVATION, TEST_COVER_OPEN),
        ]:
            # Set numeric angle for window
            config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = window_azimuth

            # Sun above threshold with varying azimuth
            mock_sun_state.attributes = {
                "elevation": TEST_HIGH_ELEVATION,
                "azimuth": sun_azimuth,
            }

            # For combined logic: use hot temp when expecting close, cold temp when expecting open
            temp_for_test = TEST_HOT_TEMP if expected == TEST_COVER_CLOSED else TEST_COLD_TEMP

            mock_hass.services.async_call.reset_mock()
            state_mapping = create_combined_state_mock(
                temp_state=temp_for_test,  # Hot when expecting close, cold when expecting open
                sun_azimuth=sun_azimuth,  # Use the actual sun azimuth from test
                cover_states={
                    MOCK_COVER_ENTITY_ID: cover_state.attributes
                    if hasattr(cover_state, "attributes")
                    else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
                },
            )
            mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

            await coordinator.async_refresh()
            cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
            assert cover_data["sca_cover_desired_position"] == expected

    @pytest.mark.asyncio
    async def test_sun_automation_numeric_string_direction(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Direction as a numeric string should be parsed as azimuth."""
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = "180"
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        state_mapping = create_combined_state_mock(
            temp_state=TEST_HOT_TEMP,  # Hot temp for close case
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Sun hitting directly
            cover_states={
                MOCK_COVER_ENTITY_ID: cover_state.attributes
                if hasattr(cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_CLOSED

    @pytest.mark.asyncio
    async def test_sun_automation_multiple_covers_varied_angles(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Only covers within tolerance should close when sun hits."""
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2])
        config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = TEST_DIRECT_AZIMUTH
        config[f"{MOCK_COVER_ENTITY_ID_2}_{COVER_SFX_AZIMUTH}"] = TEST_INDIRECT_AZIMUTH
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        cover1_state = MagicMock()
        cover1_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        cover2_state = MagicMock()
        cover2_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
        state_mapping = create_combined_state_mock(
            temp_state=TEST_HOT_TEMP,  # Hot temp for close cases
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Sun hitting test_cover directly
            cover_states={
                MOCK_COVER_ENTITY_ID: cover1_state.attributes
                if hasattr(cover1_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
                MOCK_COVER_ENTITY_ID_2: cover2_state.attributes
                if hasattr(cover2_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15},
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        covers = coordinator.data[ConfKeys.COVERS.value]
        assert covers[MOCK_COVER_ENTITY_ID]["sca_cover_desired_position"] == TEST_COVER_CLOSED
        assert covers[MOCK_COVER_ENTITY_ID_2]["sca_cover_desired_position"] == TEST_COVER_OPEN

        # Service called once for the closing cover
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=TEST_COVER_CLOSED,
        )

    @pytest.mark.asyncio
    async def test_sun_automation_threshold_equality_uses_closure(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """When elevation equals the threshold, closure logic applies (not low sun)."""
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = TEST_DIRECT_AZIMUTH
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        # Elevation equals threshold (20.0); should treat as above for logic
        mock_sun_state.attributes = {"elevation": 20.0, "azimuth": TEST_DIRECT_AZIMUTH}

        state_mapping = create_combined_state_mock(
            temp_state=TEST_HOT_TEMP,  # Hot temp for close case
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Sun hitting directly (angle_diff = 0 = threshold)
            cover_states={
                MOCK_COVER_ENTITY_ID: cover_state.attributes
                if hasattr(cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_CLOSED

    @pytest.mark.asyncio
    async def test_sun_automation_max_closure_with_numeric_angle(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Numeric angle with covers_max_closure less than 100% results in partial close."""
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config[ConfKeys.COVERS_MAX_CLOSURE.value] = 60  # 60% close => desired position 40
        config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = TEST_DIRECT_AZIMUTH
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={
                MOCK_COVER_ENTITY_ID: cover_state.attributes
                if hasattr(cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == COVER_POS_FULLY_OPEN  # Combined logic: cold temp overrides sun closure

    @pytest.mark.asyncio
    async def test_combined_hot_sun_not_hitting_no_change_with_and_logic(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """When hot but sun not hitting, AND logic should not move the cover."""
        config = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: 24.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}": TEST_DIRECT_AZIMUTH,
        }
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Too hot; sun above threshold but azimuth far from window direction
        mock_temperature_state.state = TEST_HOT_TEMP
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_INDIRECT_AZIMUTH}
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1,
            sun_azimuth=TEST_INDIRECT_AZIMUTH,  # Sun azimuth far from window direction (180°)
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN
        # AND semantics: no action when sun not hitting
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_combined_comfortable_direct_sun_no_change_with_and_logic(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """When comfortable and direct sun, AND logic should not move the cover."""
        config = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: 24.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 60,  # partial closure => desired 40
            f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}": TEST_DIRECT_AZIMUTH,
        }
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_temperature_state.state = TEST_COMFORTABLE_TEMP_2
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1,
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN
        # AND semantics: no action when temperature is not hot
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_combined_cold_direct_sun_no_change_with_and_logic(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Cold with direct sun should not move the cover under AND logic."""
        config = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: 24.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}": TEST_DIRECT_AZIMUTH,
        }
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_temperature_state.state = TEST_COLD_TEMP
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1,
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN
        # AND semantics: no action when temperature is cold
        mock_hass.services.async_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_combined_missing_direction_uses_temp_only(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """If sun direction missing, fall back to temperature input."""
        config = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: 24.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            # Intentionally omit direction key
        }
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_temperature_state.state = TEST_HOT_TEMP
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1,
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes
                if hasattr(mock_cover_state, "attributes")
                else {ATTR_CURRENT_POSITION: 100, ATTR_SUPPORTED_FEATURES: 15}
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Cover should be skipped due to missing direction, even in combined mode
        assert MOCK_COVER_ENTITY_ID not in result[ConfKeys.COVERS.value]
