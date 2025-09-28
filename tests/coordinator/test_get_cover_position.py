"""
Test the _get_cover_position method in the coordinator.

This module tests the cover position detection logic that handles both
position-supporting covers and binary covers (open/close only).
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from ..conftest import MockConfigEntry, create_temperature_config


class TestGetCoverPosition:
    """Test the _get_cover_position method logic."""

    @pytest.fixture
    def coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a DataUpdateCoordinator instance for testing."""
        config = create_temperature_config()
        config_entry = MockConfigEntry(config)
        return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

    def test_position_supporting_cover_with_current_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test position-supporting cover with valid current_position attribute."""
        # Create mock state with SET_POSITION feature and current_position
        state = MagicMock()
        state.attributes = {
            ATTR_CURRENT_POSITION: 75,
        }
        features = CoverEntityFeature.SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        assert result == 75

    def test_position_supporting_cover_without_current_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test position-supporting cover without current_position attribute."""
        # Create mock state with SET_POSITION feature but no current_position
        state = MagicMock()
        state.attributes = {}
        features = CoverEntityFeature.SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should default to fully open when current_position is missing
        assert result == const.COVER_POS_FULLY_OPEN

    def test_position_supporting_cover_none_current_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test position-supporting cover with None current_position attribute."""
        # Create mock state with SET_POSITION feature but None current_position
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: None}
        features = CoverEntityFeature.SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should default to fully open when current_position is None
        assert result == const.COVER_POS_FULLY_OPEN

    def test_binary_cover_closed_state(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover in closed state."""
        # Create mock state without SET_POSITION feature, state is closed
        state = MagicMock()
        state.state = STATE_CLOSED
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        assert result == const.COVER_POS_FULLY_CLOSED

    def test_binary_cover_open_state(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover in open state."""
        # Create mock state without SET_POSITION feature, state is open
        state = MagicMock()
        state.state = STATE_OPEN
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        assert result == const.COVER_POS_FULLY_OPEN

    def test_binary_cover_closing_state_with_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover in closing state with current_position available."""
        # Create mock state without SET_POSITION feature, state is closing
        state = MagicMock()
        state.state = STATE_CLOSING
        state.attributes = {ATTR_CURRENT_POSITION: 30}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        assert result == 30

    def test_binary_cover_opening_state_with_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover in opening state with current_position available."""
        # Create mock state without SET_POSITION feature, state is opening
        state = MagicMock()
        state.state = STATE_OPENING
        state.attributes = {ATTR_CURRENT_POSITION: 60}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        assert result == 60

    def test_binary_cover_closing_state_without_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover in closing state without current_position."""
        # Create mock state without SET_POSITION feature, state is closing, no position
        state = MagicMock()
        state.state = STATE_CLOSING
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should assume 50% when closing and no position available
        assert result == 50

    def test_binary_cover_opening_state_without_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover in opening state without current_position."""
        # Create mock state without SET_POSITION feature, state is opening, no position
        state = MagicMock()
        state.state = STATE_OPENING
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should assume 50% when opening and no position available
        assert result == 50

    def test_binary_cover_unknown_state_with_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover with unknown state but current_position available."""
        # Create mock state without SET_POSITION feature, unknown state, but has position
        state = MagicMock()
        state.state = "unknown"
        state.attributes = {ATTR_CURRENT_POSITION: 40}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should fallback to current_position when state is unknown
        assert result == 40

    def test_binary_cover_unknown_state_without_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover with unknown state and no current_position."""
        # Create mock state without SET_POSITION feature, unknown state, no position
        state = MagicMock()
        state.state = "unknown"
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should assume fully open as ultimate fallback
        assert result == const.COVER_POS_FULLY_OPEN

    def test_binary_cover_none_state_with_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover with None state but current_position available."""
        # Create mock state without SET_POSITION feature, None state, but has position
        state = MagicMock()
        state.state = None
        state.attributes = {ATTR_CURRENT_POSITION: 25}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should fallback to current_position when state is None
        assert result == 25

    def test_binary_cover_none_state_without_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover with None state and no current_position."""
        # Create mock state without SET_POSITION feature, None state, no position
        state = MagicMock()
        state.state = None
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should assume fully open as ultimate fallback
        assert result == const.COVER_POS_FULLY_OPEN

    def test_binary_cover_case_insensitive_states(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover with uppercase states (case insensitive)."""
        # Test closed state with different case
        state = MagicMock()
        state.state = "CLOSED"
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)
        assert result == const.COVER_POS_FULLY_CLOSED

        # Test open state with different case
        state.state = "Open"
        result = coordinator._get_cover_position("cover.test", state, features)
        assert result == const.COVER_POS_FULLY_OPEN

        # Test closing state with different case
        state.state = "Closing"
        result = coordinator._get_cover_position("cover.test", state, features)
        assert result == 50  # No position available, should default to 50%

    def test_binary_cover_exception_handling_state(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover when state access raises exception."""
        # Create mock state that raises exception when accessing state
        state = MagicMock()
        state.state = MagicMock(side_effect=AttributeError("No state"))
        state.attributes = {ATTR_CURRENT_POSITION: 35}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should fallback to current_position when state access fails
        assert result == 35

    def test_binary_cover_exception_handling_no_fallback(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover when state access raises exception and no position fallback."""
        # Create mock state that raises exception when accessing state, no position
        state = MagicMock()
        state.state = MagicMock(side_effect=TypeError("Invalid state"))
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should assume fully open as ultimate fallback
        assert result == const.COVER_POS_FULLY_OPEN

    def test_mixed_cover_capabilities(self, coordinator: DataUpdateCoordinator) -> None:
        """Test cover with mixed capabilities (SET_POSITION + other features)."""
        # Create mock state with multiple features including SET_POSITION
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: 85}
        features = CoverEntityFeature.SET_POSITION | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should use position logic since SET_POSITION is supported
        assert result == 85

    def test_no_features_cover(self, coordinator: DataUpdateCoordinator) -> None:
        """Test cover with no supported features."""
        # Create mock state with no features
        state = MagicMock()
        state.state = STATE_OPEN
        state.attributes = {}
        features = 0  # No features

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should still work as binary cover and return open position
        assert result == const.COVER_POS_FULLY_OPEN

    def test_float_position_conversion(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that float positions are converted to integers."""
        # Create mock state with float position
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: 67.8}
        features = CoverEntityFeature.SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should convert float to int
        assert result == 67
        assert isinstance(result, int)

    def test_edge_case_positions(self, coordinator: DataUpdateCoordinator) -> None:
        """Test edge case position values (0, 100, out of range)."""
        state = MagicMock()
        features = CoverEntityFeature.SET_POSITION

        # Test position 0 (fully closed)
        state.attributes = {ATTR_CURRENT_POSITION: 0}
        result = coordinator._get_cover_position("cover.test", state, features)
        assert result == 0

        # Test position 100 (fully open)
        state.attributes = {ATTR_CURRENT_POSITION: 100}
        result = coordinator._get_cover_position("cover.test", state, features)
        assert result == 100

        # Test negative position (should still convert)
        state.attributes = {ATTR_CURRENT_POSITION: -5}
        result = coordinator._get_cover_position("cover.test", state, features)
        assert result == -5

        # Test position over 100 (should still convert)
        state.attributes = {ATTR_CURRENT_POSITION: 150}
        result = coordinator._get_cover_position("cover.test", state, features)
        assert result == 150
