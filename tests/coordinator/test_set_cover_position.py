"""
Test the _set_cover_position method in the coordinator.

This module tests the cover position setting logic that handles both
position-supporting covers and binary covers (open/close only).
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_POSITION, CoverEntityFeature
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    Platform,
)
from homeassistant.exceptions import HomeAssistantError

from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator, ServiceCallError
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from ..conftest import MockConfigEntry, create_temperature_config


class TestSetCoverPosition:
    """Test the _set_cover_position method logic."""

    async def test_position_supporting_cover_valid_position(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test position-supporting cover with valid position value."""
        entity_id = "cover.test"
        desired_pos = 75
        features = CoverEntityFeature.SET_POSITION

        await coordinator._set_cover_position(entity_id, desired_pos, features)

        # Should call set_cover_position service
        mock_hass.services.async_call.assert_called_once_with(
            Platform.COVER, SERVICE_SET_COVER_POSITION, {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: desired_pos}
        )

    async def test_position_supporting_cover_boundary_positions(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test position-supporting cover with boundary position values."""
        entity_id = "cover.test"
        features = CoverEntityFeature.SET_POSITION

        # Test fully closed (0)
        await coordinator._set_cover_position(entity_id, 0, features)
        mock_hass.services.async_call.assert_called_with(
            Platform.COVER, SERVICE_SET_COVER_POSITION, {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 0}
        )

        # Reset mock
        mock_hass.services.async_call.reset_mock()

        # Test fully open (100)
        await coordinator._set_cover_position(entity_id, 100, features)
        mock_hass.services.async_call.assert_called_with(
            Platform.COVER, SERVICE_SET_COVER_POSITION, {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 100}
        )

    async def test_binary_cover_open_positions_above_threshold(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test binary cover with desired positions above 50% (should use open_cover service)."""
        entity_id = "cover.test"
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        # Test positions above 50 (const.COVER_POS_FULLY_OPEN / 2)
        test_positions = [51, 60, 75, 90, 100]

        for desired_pos in test_positions:
            mock_hass.services.async_call.reset_mock()

            await coordinator._set_cover_position(entity_id, desired_pos, features)

            # Should call open_cover service
            mock_hass.services.async_call.assert_called_once_with(Platform.COVER, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id})

    async def test_binary_cover_close_positions_at_or_below_threshold(
        self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock
    ) -> None:
        """Test binary cover with desired positions at or below 50% (should use close_cover service)."""
        entity_id = "cover.test"
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        # Test positions at or below 50 (const.COVER_POS_FULLY_OPEN / 2)
        test_positions = [0, 10, 25, 40, 50]

        for desired_pos in test_positions:
            mock_hass.services.async_call.reset_mock()

            await coordinator._set_cover_position(entity_id, desired_pos, features)

            # Should call close_cover service
            mock_hass.services.async_call.assert_called_once_with(Platform.COVER, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: entity_id})

    async def test_binary_cover_threshold_boundary(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test binary cover at exact threshold boundary (50% should close, 51% should open)."""
        entity_id = "cover.test"
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        # Test position 50 (exactly at threshold) - should close
        await coordinator._set_cover_position(entity_id, 50, features)
        mock_hass.services.async_call.assert_called_with(Platform.COVER, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: entity_id})

        # Reset mock
        mock_hass.services.async_call.reset_mock()

        # Test position 51 (just above threshold) - should open
        await coordinator._set_cover_position(entity_id, 51, features)
        mock_hass.services.async_call.assert_called_with(Platform.COVER, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id})

    async def test_mixed_features_cover_uses_set_position(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test cover with mixed features (SET_POSITION + others) uses SET_POSITION service."""
        entity_id = "cover.test"
        desired_pos = 65
        features = CoverEntityFeature.SET_POSITION | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP

        await coordinator._set_cover_position(entity_id, desired_pos, features)

        # Should call set_cover_position service (not binary open/close)
        mock_hass.services.async_call.assert_called_once_with(
            Platform.COVER, SERVICE_SET_COVER_POSITION, {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: desired_pos}
        )

    async def test_no_features_cover_uses_binary_logic(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test cover with no features still uses binary open/close logic."""
        entity_id = "cover.test"
        features = 0  # No features

        # Test above threshold - should open
        await coordinator._set_cover_position(entity_id, 80, features)
        mock_hass.services.async_call.assert_called_with(Platform.COVER, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id})

        # Reset mock
        mock_hass.services.async_call.reset_mock()

        # Test below threshold - should close
        await coordinator._set_cover_position(entity_id, 20, features)
        mock_hass.services.async_call.assert_called_with(Platform.COVER, SERVICE_CLOSE_COVER, {ATTR_ENTITY_ID: entity_id})

    async def test_simulation_mode_skips_service_call(self, mock_hass: MagicMock) -> None:
        """Test that simulation mode skips actual service calls."""
        # Create config with simulation enabled
        config = create_temperature_config()
        config["simulating"] = True
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        entity_id = "cover.test"
        desired_pos = 75
        features = CoverEntityFeature.SET_POSITION

        await coordinator._set_cover_position(entity_id, desired_pos, features)

        # Should not call any service in simulation mode
        mock_hass.services.async_call.assert_not_called()

    async def test_position_validation_out_of_range_low(self, coordinator: DataUpdateCoordinator) -> None:
        """Test position validation with value below valid range."""
        entity_id = "cover.test"
        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ValueError, match="desired_pos must be between 0 and 100, got -10"):
            await coordinator._set_cover_position(entity_id, -10, features)

    async def test_position_validation_out_of_range_high(self, coordinator: DataUpdateCoordinator) -> None:
        """Test position validation with value above valid range."""
        entity_id = "cover.test"
        features = CoverEntityFeature.SET_POSITION

        with pytest.raises(ValueError, match="desired_pos must be between 0 and 100, got 150"):
            await coordinator._set_cover_position(entity_id, 150, features)

    async def test_service_call_error_handling_home_assistant_error(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test error handling when Home Assistant service call fails."""
        entity_id = "cover.test"
        desired_pos = 50
        features = CoverEntityFeature.SET_POSITION

        # Mock service call to raise HomeAssistantError
        mock_hass.services.async_call.side_effect = HomeAssistantError("Service not found")

        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(entity_id, desired_pos, features)

    async def test_service_call_error_handling_connection_error(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test error handling when connection error occurs."""
        entity_id = "cover.test"
        desired_pos = 50
        features = CoverEntityFeature.SET_POSITION

        # Mock service call to raise ConnectionError
        mock_hass.services.async_call.side_effect = ConnectionError("Connection lost")

        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(entity_id, desired_pos, features)

    async def test_service_call_error_preserves_service_name_for_binary_covers(
        self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock
    ) -> None:
        """Test that error messages correctly identify the service for binary covers."""
        entity_id = "cover.test"
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        # Test open service error
        mock_hass.services.async_call.side_effect = HomeAssistantError("Service failed")

        with pytest.raises(ServiceCallError, match="Failed to call open_cover"):
            await coordinator._set_cover_position(entity_id, 80, features)  # Above threshold

        # Reset mock for close service test
        mock_hass.services.async_call.reset_mock()
        mock_hass.services.async_call.side_effect = HomeAssistantError("Service failed")

        with pytest.raises(ServiceCallError, match="Failed to call close_cover"):
            await coordinator._set_cover_position(entity_id, 20, features)  # Below threshold

    async def test_service_call_error_handling_value_error(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test error handling when ValueError occurs during service call."""
        entity_id = "cover.test"
        desired_pos = 50
        features = CoverEntityFeature.SET_POSITION

        # Mock service call to raise ValueError
        mock_hass.services.async_call.side_effect = ValueError("Invalid entity ID format")

        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(entity_id, desired_pos, features)

    async def test_service_call_error_handling_type_error(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test error handling when TypeError occurs during service call."""
        entity_id = "cover.test"
        desired_pos = 50
        features = CoverEntityFeature.SET_POSITION

        # Mock service call to raise TypeError
        mock_hass.services.async_call.side_effect = TypeError("'NoneType' object is not callable")

        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(entity_id, desired_pos, features)

    async def test_service_call_error_handling_unexpected_error(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test error handling when unexpected error occurs during service call."""
        entity_id = "cover.test"
        desired_pos = 50
        features = CoverEntityFeature.SET_POSITION

        # Mock service call to raise unexpected error
        mock_hass.services.async_call.side_effect = RuntimeError("Unexpected runtime error")

        with pytest.raises(ServiceCallError, match="Failed to call set_cover_position"):
            await coordinator._set_cover_position(entity_id, desired_pos, features)

    async def test_various_entity_ids_and_positions(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test method works with various entity IDs and position combinations."""
        test_cases = [
            ("cover.living_room", 25, CoverEntityFeature.SET_POSITION),
            ("cover.bedroom_window", 75, CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE),
            ("cover.kitchen", 0, CoverEntityFeature.SET_POSITION),
            ("cover.office", 100, CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE),
        ]

        for entity_id, desired_pos, features in test_cases:
            mock_hass.services.async_call.reset_mock()

            await coordinator._set_cover_position(entity_id, desired_pos, features)

            # Verify service was called (exact service depends on features and position)
            mock_hass.services.async_call.assert_called_once()
            call_args = mock_hass.services.async_call.call_args

            # All calls should be to cover platform
            assert call_args[0][0] == Platform.COVER

            # Service data should include the entity_id
            service_data = call_args[0][2]
            assert service_data[ATTR_ENTITY_ID] == entity_id

    async def test_return_value_position_supporting_covers(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test that position-supporting covers return the exact desired position."""
        entity_id = "cover.test"
        features = CoverEntityFeature.SET_POSITION

        test_positions = [0, 25, 50, 75, 100]

        for desired_pos in test_positions:
            actual_pos = await coordinator._set_cover_position(entity_id, desired_pos, features)

            # For position-supporting covers, actual should equal desired
            assert actual_pos == desired_pos

    async def test_return_value_binary_covers_above_threshold(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test that binary covers return 100 for positions above threshold."""
        entity_id = "cover.test"
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        # Test positions above 50% threshold
        test_positions = [51, 60, 75, 90, 100]

        for desired_pos in test_positions:
            actual_pos = await coordinator._set_cover_position(entity_id, desired_pos, features)

            # Binary covers above threshold should return fully open (100)
            assert actual_pos == 100

    async def test_return_value_binary_covers_at_or_below_threshold(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test that binary covers return 0 for positions at or below threshold."""
        entity_id = "cover.test"
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        # Test positions at or below 50% threshold
        test_positions = [0, 10, 25, 40, 50]

        for desired_pos in test_positions:
            actual_pos = await coordinator._set_cover_position(entity_id, desired_pos, features)

            # Binary covers at/below threshold should return fully closed (0)
            assert actual_pos == 0

    async def test_return_value_simulation_mode(self, mock_hass: MagicMock) -> None:
        """Test that simulation mode still returns correct actual position values."""
        # Create config with simulation enabled
        config = create_temperature_config()
        config["simulating"] = True
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Test position-supporting cover in simulation mode
        actual_pos = await coordinator._set_cover_position("cover.test", 75, CoverEntityFeature.SET_POSITION)
        assert actual_pos == 75

        # Test binary cover above threshold in simulation mode
        actual_pos = await coordinator._set_cover_position("cover.test", 80, CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE)
        assert actual_pos == 100

        # Test binary cover below threshold in simulation mode
        actual_pos = await coordinator._set_cover_position("cover.test", 20, CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE)
        assert actual_pos == 0

        # Should not call any service in simulation mode
        mock_hass.services.async_call.assert_not_called()

    async def test_return_value_boundary_cases(self, coordinator: DataUpdateCoordinator, mock_hass: MagicMock) -> None:
        """Test return values for boundary cases."""
        entity_id = "cover.test"

        # Test position-supporting cover at boundaries
        features = CoverEntityFeature.SET_POSITION
        assert await coordinator._set_cover_position(entity_id, 0, features) == 0
        assert await coordinator._set_cover_position(entity_id, 100, features) == 100

        # Test binary cover at exact threshold boundary
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

        # Position 50 (at threshold) should return 0 (close)
        assert await coordinator._set_cover_position(entity_id, 50, features) == 0

        # Position 51 (above threshold) should return 100 (open)
        assert await coordinator._set_cover_position(entity_id, 51, features) == 100
