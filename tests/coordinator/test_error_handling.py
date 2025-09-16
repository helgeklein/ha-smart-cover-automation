"""Error handling and edge case tests.

This module contains comprehensive tests for error conditions, edge cases,
and exception handling in the DataUpdateCoordinator, including service failures,
missing entities, invalid configurations, and cover compatibility issues.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import (
    AllCoversUnavailableError,
    ConfigurationError,
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
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestErrorHandling(TestDataUpdateCoordinatorBase):
    """Test suite for error handling and edge cases."""

    async def test_cover_unavailable(
        self,
        coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test error handling when all configured covers are unavailable.

        Validates that the coordinator properly detects and reports when all
        configured cover entities are missing from Home Assistant's state registry.
        This ensures proper error reporting when covers are temporarily unavailable
        or misconfigured.

        Test scenario:
        - Temperature and sun sensors: Available
        - All cover entities: Missing from state registry
        - Expected behavior: AllCoversUnavailableError raised and captured
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
        assert isinstance(coordinator.last_exception, AllCoversUnavailableError)

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
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        # Mock service call to fail
        mock_hass.services.async_call.side_effect = OSError("Service failed")

        state_mapping = create_combined_state_mock(
            temp_state=mock_temperature_state.state,
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
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=mock_temperature_state.state,
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
    ) -> None:
        """Test configuration validation when no covers are specified.

        Validates that the automation properly validates configuration and reports
        errors when the covers list is empty. This prevents the automation from
        running without any target devices to control.

        Test scenario:
        - Configuration: Empty covers list
        - Expected behavior: ConfigurationError raised with descriptive message
        """
        config = create_temperature_config()
        config[ConfKeys.COVERS.value] = []
        config_entry = MockConfigEntry(config)

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))
        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, ConfigurationError)
        assert "No covers configured" in str(coordinator.last_exception)

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
