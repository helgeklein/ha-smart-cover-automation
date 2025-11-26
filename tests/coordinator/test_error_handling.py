"""Error handling and edge case tests.

This module contains comprehensive tests for error conditions, edge cases,
and exception handling in the DataUpdateCoordinator, including service failures,
missing entities, invalid configurations, and cover compatibility issues.
"""

from __future__ import annotations

import logging
from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES, Platform

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_ATTR_SUN_HITTING,
    COVER_SFX_AZIMUTH,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from custom_components.smart_cover_automation.ha_interface import ServiceCallError
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_COVER_ENTITY_ID_2,
    MOCK_SUN_ENTITY_ID,
    MOCK_WEATHER_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COMFORTABLE_TEMP_1,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    MockConfigEntry,
    assert_service_called,
    create_combined_state_mock,
    create_sun_config,
    create_temperature_config,
    set_weather_forecast_temp,
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestErrorHandling(TestDataUpdateCoordinatorBase):
    """Test suite for error handling and edge cases."""

    async def test_cover_unavailable(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_temperature_state: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test graceful error handling when all configured covers are unavailable.

        Validates that the coordinator gracefully handles and reports when all
        configured cover entities are missing from Home Assistant's state registry.
        The system should log the error but continue operation with minimal state
        to keep integration entities available.

        Test scenario:
        - Temperature and sun sensors: Available
        - All cover entities: Missing from state registry
        - Expected behavior: Error logged, minimal state returned, no exception raised
        """
        # Manually create state mapping without any covers, but with temp and sun sensors
        temp_mock = MagicMock()
        temp_mock.entity_id = MOCK_WEATHER_ENTITY_ID
        temp_mock.state = mock_temperature_state.state if hasattr(mock_temperature_state, "state") else TEST_COMFORTABLE_TEMP_1

        sun_mock = MagicMock()
        sun_mock.entity_id = MOCK_SUN_ENTITY_ID
        sun_mock.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        state_mapping = {
            MOCK_WEATHER_ENTITY_ID: temp_mock,
            MOCK_SUN_ENTITY_ID: sun_mock,
            # No covers in state mapping - they will be unavailable
        }

        # Set caplog to capture INFO level messages
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)
        await coordinator.async_refresh()

        # Verify graceful error handling
        assert coordinator.last_exception is None  # No exception should propagate
        assert coordinator.data.covers == {}  # Minimal valid state returned
        assert "All covers unavailable; skipping actions" in caplog.text

    async def test_service_call_failure(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test graceful handling of Home Assistant service call failures.

        Validates that when Home Assistant cover service calls fail (network issues,
        device problems, etc.), the automation continues to function and reports
        data without crashing. This ensures system stability during hardware failures.

        Test scenario:
        - Automation logic: Determines covers should close (hot temperature)
        - Service call: Fails with OSError
        - Expected behavior: Automation completes, data available, no crash
        """
        # Setup - temperature too hot, should close covers
        mock_temperature_state.state = TEST_HOT_TEMP
        set_weather_forecast_temp(float(mock_temperature_state.state))
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        # Mock cover service calls to fail, but allow weather service calls to succeed
        # Get the original weather service mock from conftest
        original_weather_mock = mock_hass._weather_service_mock

        async def selective_service_failure(domain, service, service_data, **kwargs):
            if domain == Platform.COVER:
                raise OSError("Service failed")
            # Delegate weather service calls to the original mock
            return await original_weather_mock(domain, service, service_data, **kwargs)

        mock_hass.services.async_call.side_effect = selective_service_failure

        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute - should not raise exception, just log error
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify - automation still completes despite service failure
        assert result is not None
        assert MOCK_COVER_ENTITY_ID in result.covers

    async def test_cover_without_position_support(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test automation with covers that don't support position control.

        Validates that the automation adapts to covers with limited capabilities,
        using basic open/close commands instead of position commands when
        SET_POSITION feature is not available. This ensures compatibility with
        older or simpler cover devices.

        Test scenario:
        - Cover capabilities: Only OPEN and CLOSE (no SET_POSITION)
        - Temperature: Hot (should trigger closure)
        - Expected action: close_cover service called instead of set_cover_position
        """
        # Setup cover without position support
        mock_cover_state.attributes[ATTR_SUPPORTED_FEATURES] = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        mock_temperature_state.state = TEST_HOT_TEMP  # Too hot
        set_weather_forecast_temp(float(mock_temperature_state.state))
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes,
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
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test graceful configuration validation when no covers are specified.

        Validates that the automation gracefully handles configuration validation
        and reports errors when the covers list is empty. The system should log
        the error but continue operation with minimal state to keep integration
        entities available.

        Test scenario:
        - Configuration: Empty covers list
        - Expected behavior: Error logged, minimal state returned, no exception raised
        """
        config = create_temperature_config()
        config[ConfKeys.COVERS.value] = []
        config_entry = MockConfigEntry(config)

        # Set caplog to capture INFO level messages
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        await coordinator.async_refresh()

        # Verify graceful error handling
        assert coordinator.last_exception is None  # No exception should propagate
        assert coordinator.data.covers == {}  # Minimal valid state returned
        assert "No covers configured; skipping actions" in caplog.text

    async def test_service_call_error_class_init(self) -> None:
        """Test ServiceCallError exception class initialization.

        Validates that the custom ServiceCallError exception class properly
        initializes with service, entity, and error information for comprehensive
        error reporting and debugging.

        Test scenario:
        - Create ServiceCallError with test parameters
        - Verify error message formatting and attribute access
        """
        err = ServiceCallError("cover.set_cover_position", "cover.test", "boom")
        assert "Failed to call" in str(err)
        assert err.service == "cover.set_cover_position"
        assert err.entity_id == "cover.test"

    async def test_sun_entity_missing(
        self,
        mock_hass: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test critical error handling when sun entity is not found in Home Assistant.

        Validates that the coordinator treats missing sun entity as a critical error
        that makes the automation non-functional. Since sun position is essential for
        automation decisions, missing sun entity should make entities unavailable.

        Test scenario:
        - Sun entity: Missing from Home Assistant state registry
        - Expected behavior: Critical error logged, UpdateFailed exception raised, entities unavailable
        """
        from homeassistant.helpers.update_coordinator import UpdateFailed

        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Create state mapping WITHOUT sun entity (to simulate missing sensor)
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        state_mapping = {
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_WEATHER_ENTITY_ID: MagicMock(entity_id=MOCK_WEATHER_ENTITY_ID, state=TEST_COMFORTABLE_TEMP_1),
            # MOCK_SUN_ENTITY_ID is intentionally missing
        }

        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)
        await coordinator.async_refresh()

        # Verify critical error handling - sun sensor missing
        assert isinstance(coordinator.last_exception, UpdateFailed)  # Critical error should propagate
        assert "Sun sensor 'sun.sun' not found" in str(coordinator.last_exception)

    async def test_sun_entity_invalid_data(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test graceful error handling when sun entity provides invalid data.

        Validates that the coordinator gracefully handles invalid sun sensor readings
        by logging a warning and skipping automation actions. This ensures system
        stability when sun sensor data is temporarily invalid.

        Test scenario:
        - Sun entity: Returns "invalid" string for elevation
        - Expected behavior: Warning logged, minimal state returned, no exception raised
        """
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Set caplog to capture INFO level messages
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        mock_sun_state.attributes = {"elevation": "invalid", "azimuth": TEST_DIRECT_AZIMUTH}
        mock_hass.states.get.return_value = mock_sun_state
        await coordinator.async_refresh()

        # Verify graceful error handling
        assert coordinator.last_exception is None  # No exception should propagate
        assert coordinator.data.covers == {}  # Minimal valid state returned
        assert "Sun elevation unavailable" in caplog.text

    async def test_cover_missing_azimuth_configuration(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that covers without azimuth configuration are skipped in sun automation.

        Validates that covers missing window orientation configuration are excluded
        from sun automation but can still participate in temperature automation.

        Test scenario:
        - Two covers configured
        - Second cover missing azimuth/direction configuration
        - Expected behavior: Second cover skipped from sun automation
        """
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

        # Set weather forecast temperature for cold temperature
        set_weather_forecast_temp(float(TEST_COLD_TEMP))  # Cold temp so temp wants open

        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                MOCK_COVER_ENTITY_ID_2: cover2_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Both covers should appear (cover 2 has lock data even though azimuth is missing)
        covers_dict = result.covers
        assert MOCK_COVER_ENTITY_ID in covers_dict
        assert MOCK_COVER_ENTITY_ID_2 in covers_dict

        # Cover 1 should have both temperature and sun automation data
        cover1_data = result.covers[MOCK_COVER_ENTITY_ID]
        assert result.temp_hot is not None
        assert COVER_ATTR_SUN_HITTING in cover1_data

        # Cover 2 should only have lock data (no sun_hitting due to missing azimuth)
        cover2_data = result.covers[MOCK_COVER_ENTITY_ID_2]
        assert COVER_ATTR_SUN_HITTING not in cover2_data
        assert "cover_lock_mode" in cover2_data
        assert "cover_lock_active" in cover2_data

    async def test_cover_invalid_azimuth_configuration(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that covers with invalid azimuth configuration are skipped.

        Validates that covers with invalid direction strings (non-numeric, non-cardinal)
        are excluded from sun automation with proper error handling.

        Test scenario:
        - Two covers configured
        - Second cover has invalid azimuth ("upwards")
        - Expected behavior: Second cover skipped from sun automation
        """
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

        # Set weather forecast temperature for cold temperature
        set_weather_forecast_temp(float(TEST_COLD_TEMP))  # Cold temp so temp wants open

        state_mapping = create_combined_state_mock(
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                MOCK_COVER_ENTITY_ID_2: cover2_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Both covers should appear (cover 2 has lock data even though azimuth is invalid)
        covers_dict = result.covers
        assert MOCK_COVER_ENTITY_ID in covers_dict
        assert MOCK_COVER_ENTITY_ID_2 in covers_dict

        # Cover 1 should have both temperature and sun automation data
        cover1_data = result.covers[MOCK_COVER_ENTITY_ID]
        assert result.temp_hot is not None
        assert COVER_ATTR_SUN_HITTING in cover1_data

        # Cover 2 should only have lock data (no sun_hitting due to invalid azimuth)
        cover2_data = result.covers[MOCK_COVER_ENTITY_ID_2]
        assert COVER_ATTR_SUN_HITTING not in cover2_data
        assert "cover_lock_mode" in cover2_data
        assert "cover_lock_active" in cover2_data

    async def test_sun_azimuth_unavailable(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test coordinator lines 257-259: Sun azimuth unavailable; skipping actions.

        Validates that when sun azimuth data is not available or invalid,
        the automation gracefully skips all actions and logs a warning.

        Test scenario:
        - Sun elevation: Available
        - Sun azimuth: Missing/invalid (None)
        - Expected behavior: Skip all actions, return result with warning message
        """
        # Setup - valid temperature and cover, but invalid sun azimuth
        mock_temperature_state.state = TEST_COMFORTABLE_TEMP_1
        set_weather_forecast_temp(float(mock_temperature_state.state))

        # Create state mapping with invalid sun azimuth
        state_mapping = create_combined_state_mock(
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
            sun_elevation=TEST_HIGH_ELEVATION,
            sun_azimuth=TEST_DIRECT_AZIMUTH,
        )
        # Manually override sun state to have None azimuth
        sun_mock = state_mapping[MOCK_SUN_ENTITY_ID]
        sun_mock.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": None}
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Set caplog to capture INFO level messages
        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Execute
        await coordinator.async_refresh()
        result = coordinator.data

        # Verify - should skip actions due to invalid sun azimuth
        assert result.covers == {}
        assert "Sun azimuth unavailable" in caplog.text
