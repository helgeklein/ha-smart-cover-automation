"""Temperature-based automation tests.

This module contains comprehensive tests for temperature-based automation logic
in the DataUpdateCoordinator, including hot/cold/comfortable temperature handling
and error conditions related to temperature sensors.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES, Platform
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import (
    DataUpdateCoordinator,
)
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_COVER_ENTITY_ID_2,
    MOCK_SUN_ENTITY_ID,
    MOCK_WEATHER_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COMFORTABLE_TEMP_1,
    TEST_COMFORTABLE_TEMP_2,
    TEST_COVER_CLOSED,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    TEST_INDIRECT_AZIMUTH,
    TEST_PARTIAL_POSITION,
    assert_service_called,
    create_combined_state_mock,
    set_weather_forecast_temp,
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestTemperatureAutomation(TestDataUpdateCoordinatorBase):
    """Test suite for temperature-based automation logic."""

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

        # Set weather forecast temperature for hot temperature
        set_weather_forecast_temp(float(TEST_HOT_TEMP))  # 26.0°C - above 24°C threshold

        # Create environmental state: hot temperature + sun hitting window
        # Both conditions met for AND logic to trigger cover closing
        state_mapping = create_combined_state_mock(
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

        # Set weather forecast temperature for cold temperature
        set_weather_forecast_temp(float(TEST_COLD_TEMP))  # 18.0°C - below 21°C threshold

        # Create environmental state: cold temperature + sun not hitting window
        # Cold temperature condition met for opening (sun position secondary)
        state_mapping = create_combined_state_mock(
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

        # Set weather forecast temperature for comfortable temperature
        temp_for_test = mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1
        set_weather_forecast_temp(float(temp_for_test))

        # Create environmental state with comfortable temperature
        state_mapping = create_combined_state_mock(
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
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test critical error handling when temperature sensor is not found in Home Assistant.

        Validates that the coordinator treats missing temperature sensor as a critical error
        that makes the automation non-functional. Since temperature readings are essential for
        automation decisions, missing temperature sensor should make entities unavailable.

        Test scenario:
        - Temperature sensor: Missing from Home Assistant state registry
        - Cover entities: Available and properly configured
        - Expected behavior: Critical error logged, UpdateFailed exception raised, entities unavailable
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
            # MOCK_WEATHER_ENTITY_ID is intentionally missing
        }

        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute automation and verify error handling
        await coordinator.async_refresh()

        # Verify critical error handling
        assert isinstance(coordinator.last_exception, UpdateFailed)  # Critical error should propagate
        assert "Temperature sensor 'weather.forecast' not found" in str(coordinator.last_exception)

    async def test_temperature_sensor_invalid_reading(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_temperature_state: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test critical error handling when weather forecast is unavailable.

        Validates that the coordinator treats unavailable weather forecast as critical errors
        that make the automation non-functional. Since accurate temperature readings are essential for
        automation decisions, unavailable forecast data should make entities unavailable.

        Test scenario:
        - Weather entity: Available but forecast service returns no data
        - Expected behavior: Critical error logged, UpdateFailed exception raised, entities unavailable
        """
        # Setup weather entity state
        mock_temperature_state.state = "sunny"
        mock_temperature_state.entity_id = MOCK_WEATHER_ENTITY_ID
        mock_hass.states.get.return_value = mock_temperature_state

        # Mock weather service to return no forecast data (simulating service failure)
        async def mock_weather_service_error(domain, service, service_data, **kwargs):
            if domain == Platform.WEATHER and service == "get_forecasts":
                return {}  # Empty response simulating forecast unavailable
            return {}

        mock_hass.services.async_call = AsyncMock(side_effect=mock_weather_service_error)

        # Execute automation and verify error handling
        await coordinator.async_refresh()

        # Verify critical error handling
        assert isinstance(coordinator.last_exception, UpdateFailed)  # Critical error should propagate
        assert "Forecast temperature unavailable" in str(coordinator.last_exception)
