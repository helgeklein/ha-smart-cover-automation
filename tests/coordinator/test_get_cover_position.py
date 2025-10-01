"""
Test the _get_cover_position method in the coordinator.

This module tests the cover position detection logic that handles both
position-supporting covers and binary covers (open/close only).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


class TestGetCoverPosition:
    """Test the _get_cover_position method logic."""

    @pytest.mark.parametrize(
        "current_position, expected_result",
        [
            (75, 75),  # Valid position
            (0, 0),  # Minimum position
            (100, 100),  # Maximum position
            (50, 50),  # Middle position
        ],
    )
    def test_position_supporting_cover_with_current_position(
        self, coordinator: DataUpdateCoordinator, current_position: int, expected_result: int
    ) -> None:
        """Test position-supporting cover with various valid current_position values."""
        # Create mock state with SET_POSITION feature and current_position
        state = MagicMock()
        state.attributes = {
            ATTR_CURRENT_POSITION: current_position,
        }
        features = CoverEntityFeature.SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        assert result == expected_result

    @pytest.mark.parametrize(
        "missing_position_value",
        [
            None,  # None value
            {},  # Missing attribute (empty dict)
        ],
    )
    def test_position_supporting_cover_without_current_position(self, coordinator: DataUpdateCoordinator, missing_position_value) -> None:
        """Test position-supporting cover without current_position attribute."""
        # Create mock state with SET_POSITION feature but no/invalid current_position
        state = MagicMock()
        if missing_position_value is None:
            state.attributes = {ATTR_CURRENT_POSITION: None}
        else:
            state.attributes = missing_position_value
        features = CoverEntityFeature.SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should default to fully open when current_position is missing
        assert result == const.COVER_POS_FULLY_OPEN

    @pytest.mark.parametrize(
        "cover_state, expected_position",
        [
            (STATE_CLOSED, const.COVER_POS_FULLY_CLOSED),
            (STATE_OPEN, const.COVER_POS_FULLY_OPEN),
        ],
    )
    def test_binary_cover_fixed_states(self, coordinator: DataUpdateCoordinator, cover_state: str, expected_position: int) -> None:
        """Test binary cover in closed or open states."""
        # Create mock state without SET_POSITION feature
        state = MagicMock()
        state.state = cover_state
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        assert result == expected_position

    @pytest.mark.parametrize(
        "cover_state, current_position, expected_result",
        [
            (STATE_CLOSING, 30, const.COVER_POS_FULLY_OPEN),  # Closing defaults to fully open
            (STATE_OPENING, 60, const.COVER_POS_FULLY_OPEN),  # Opening defaults to fully open
            ("unknown", 40, const.COVER_POS_FULLY_OPEN),  # Unknown state defaults to fully open
            ("unavailable", 25, const.COVER_POS_FULLY_OPEN),  # Unavailable state defaults to fully open
        ],
    )
    def test_binary_cover_transitional_states_with_position(
        self, coordinator: DataUpdateCoordinator, cover_state: str, current_position: int, expected_result: int
    ) -> None:
        """Test binary cover in transitional states with current_position available."""
        # Create mock state without SET_POSITION feature, with position
        state = MagicMock()
        state.state = cover_state
        state.attributes = {ATTR_CURRENT_POSITION: current_position}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        assert result == expected_result

    @pytest.mark.parametrize(
        "cover_state, expected_position",
        [
            (STATE_CLOSING, const.COVER_POS_FULLY_OPEN),  # Transitional state defaults to fully open
            (STATE_OPENING, const.COVER_POS_FULLY_OPEN),  # Transitional state defaults to fully open
            ("unknown", const.COVER_POS_FULLY_OPEN),  # Unknown state falls back to fully open
            ("unavailable", const.COVER_POS_FULLY_OPEN),  # Unavailable state falls back to fully open
        ],
    )
    def test_binary_cover_transitional_states_without_position(
        self, coordinator: DataUpdateCoordinator, cover_state: str, expected_position: int
    ) -> None:
        """Test binary cover in transitional states without current_position."""
        # Create mock state without SET_POSITION feature, no position
        state = MagicMock()
        state.state = cover_state
        state.attributes = {}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Verify expected position based on state
        assert result == expected_position

    def test_binary_cover_none_state_with_position(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover with None state but current_position available."""
        # Create mock state without SET_POSITION feature, None state, but has position
        state = MagicMock()
        state.state = None
        state.attributes = {ATTR_CURRENT_POSITION: 25}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should fallback to default position when state is None
        assert result == const.COVER_POS_FULLY_OPEN

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
        assert result == const.COVER_POS_FULLY_OPEN  # No position available, should default to fully open

    def test_binary_cover_exception_handling_state(self, coordinator: DataUpdateCoordinator) -> None:
        """Test binary cover when state access raises exception."""
        # Create mock state that raises exception when accessing state
        state = MagicMock()
        state.state = MagicMock(side_effect=AttributeError("No state"))
        state.attributes = {ATTR_CURRENT_POSITION: 35}
        features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE  # No SET_POSITION

        result = coordinator._get_cover_position("cover.test", state, features)

        # Should fallback to default position when state access fails
        assert result == const.COVER_POS_FULLY_OPEN

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
