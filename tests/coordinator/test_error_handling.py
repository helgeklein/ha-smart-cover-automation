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
from custom_components.smart_cover_automation.coordinator import (
    DataUpdateCoordinator,
    ServiceCallError,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_COVER_ENTITY_ID_2,
    MOCK_SUN_ENTITY_ID,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    TEST_COMFORTABLE_TEMP_1,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    MockConfigEntry,
    assert_service_called,
    create_combined_state_mock,
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

        # Verify graceful error handling
        assert coordinator.last_exception is None  # No exception should propagate
        assert coordinator.data == {ConfKeys.COVERS.value: {}}  # Minimal valid state returned
        assert "All covers unavailable; skipping actions" in caplog.text  # Error should be logged

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
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]

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

        # Set caplog to capture warning level messages
        caplog.set_level(logging.WARNING, logger="custom_components.smart_cover_automation")

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        await coordinator.async_refresh()

        # Verify graceful error handling
        assert coordinator.last_exception is None  # No exception should propagate
        assert coordinator.data == {ConfKeys.COVERS.value: {}}  # Minimal valid state returned
        assert "No covers configured; skipping actions" in caplog.text  # Error should be logged

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
