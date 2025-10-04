"""Test position history tracking functionality in the coor        # Verify internal storage maintains only last two
assert coordinator._cover_position_history == {"cover.test": [100, 80]}nator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.smart_cover_automation.const import (
    COVER_POSITION_HISTORY_SIZE,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


class TestPositionHistory:
    """Test position history tracking functionality."""

    @pytest.mark.asyncio
    async def test_position_history_initialization(self, coordinator: DataUpdateCoordinator):
        """Test that position history starts empty."""
        # Initially empty position history - check via the getter method
        history = coordinator._get_cover_position_history("cover.non_existent")
        assert history == []

        # Test getting history for non-existent cover
        history = coordinator._get_cover_position_history("cover.non_existent")
        assert history == []

    @pytest.mark.asyncio
    async def test_position_history_single_update(self, coordinator: DataUpdateCoordinator):
        """Test position history with a single position update."""
        # Update position once
        coordinator._update_cover_position_history("cover.test", 50)

        # Check history - first update should be current, no previous
        history = coordinator._get_cover_position_history("cover.test")
        assert history == [50]

        # Verify internal storage uses deque - check that it was initialized
        assert hasattr(coordinator, "_cover_position_history")
        assert "cover.test" in coordinator._cover_position_history
        assert list(coordinator._cover_position_history["cover.test"]) == [50]

    @pytest.mark.asyncio
    async def test_position_history_two_updates(self, coordinator: DataUpdateCoordinator):
        """Test position history with two position updates."""
        # Update position twice
        coordinator._update_cover_position_history("cover.test", 30)
        coordinator._update_cover_position_history("cover.test", 70)

        # Check history - should have current and previous
        history = coordinator._get_cover_position_history("cover.test")
        assert history == [70, 30]

        # Verify internal storage maintains newest first order - ensure it was initialized
        assert hasattr(coordinator, "_cover_position_history")
        assert list(coordinator._cover_position_history["cover.test"]) == [70, 30]

    @pytest.mark.asyncio
    async def test_position_history_multiple_updates(self, coordinator: DataUpdateCoordinator):
        """Test position history with multiple updates (uses COVER_POSITION_HISTORY_SIZE limit)."""
        # Update position multiple times - add more than the limit to test maxlen behavior
        positions = [10, 40, 80, 100, 60]
        for pos in positions:
            coordinator._update_cover_position_history("cover.test", pos)

        # Check history - should keep last COVER_POSITION_HISTORY_SIZE positions in newest-first order
        history = coordinator._get_cover_position_history("cover.test")
        # Take last 3 positions: [80, 100, 60] and put in newest-first order: [60, 100, 80]
        expected_positions = [60, 100, 80]  # newest first order

        assert history == expected_positions

        # Verify internal storage - ensure it was initialized
        assert hasattr(coordinator, "_cover_position_history")
        assert list(coordinator._cover_position_history["cover.test"]) == expected_positions

        # Add one more to test maxlen behavior
        coordinator._update_cover_position_history("cover.test", 20)
        history = coordinator._get_cover_position_history("cover.test")

        # Now we should have: [20, 60, 100] (newest first, 80 dropped)
        assert history == [20, 60, 100]

    @pytest.mark.asyncio
    async def test_position_history_multiple_covers(self, coordinator: DataUpdateCoordinator):
        """Test position history with multiple covers."""
        # Update positions for different covers
        coordinator._update_cover_position_history("cover.test1", 25)
        coordinator._update_cover_position_history("cover.test2", 75)
        coordinator._update_cover_position_history("cover.test1", 50)

        # Check history for first cover
        history1 = coordinator._get_cover_position_history("cover.test1")
        assert history1 == [50, 25]

        # Check history for second cover
        history2 = coordinator._get_cover_position_history("cover.test2")
        assert history2 == [75]

        # Verify internal storage for each cover is independent
        assert list(coordinator._cover_position_history["cover.test1"]) == [50, 25]
        assert list(coordinator._cover_position_history["cover.test2"]) == [75]

    @pytest.mark.asyncio
    async def test_position_history_same_position_updates(self, coordinator: DataUpdateCoordinator):
        """Test position history when same position is set multiple times."""
        # Update with same position multiple times
        coordinator._update_cover_position_history("cover.test", 60)
        coordinator._update_cover_position_history("cover.test", 60)
        coordinator._update_cover_position_history("cover.test", 60)

        # Should still track each update even if position is same
        history = coordinator._get_cover_position_history("cover.test")
        assert history == [60, 60, 60]

        # Verify internal storage
        assert list(coordinator._cover_position_history["cover.test"]) == [60, 60, 60]

    @pytest.mark.asyncio
    async def test_position_history_none_values(self, coordinator: DataUpdateCoordinator):
        """Test position history with None position values."""
        # Update with None and then valid position
        coordinator._update_cover_position_history("cover.test", None)
        coordinator._update_cover_position_history("cover.test", 45)

        # Check history
        history = coordinator._get_cover_position_history("cover.test")
        assert history == [45, None]

        # Verify internal storage
        assert list(coordinator._cover_position_history["cover.test"]) == [45, None]

    @pytest.mark.asyncio
    async def test_position_history_edge_case_positions(self, coordinator: DataUpdateCoordinator):
        """Test position history with edge case position values."""
        # Update with edge case positions
        coordinator._update_cover_position_history("cover.test", 0)
        coordinator._update_cover_position_history("cover.test", 100)

        # Check history
        history = coordinator._get_cover_position_history("cover.test")
        assert history == [100, 0]

    @pytest.mark.asyncio
    async def test_position_history_integration_with_set_cover_position(self, coordinator: DataUpdateCoordinator):
        """Test that position history is updated when _set_cover_position is called and position is manually updated."""
        # Mock the hass and cover entity
        coordinator.hass.states.get = MagicMock()
        coordinator.hass.services.async_call = AsyncMock()

        # Mock cover state with position support
        mock_cover_state = MagicMock()
        mock_cover_state.attributes = {"supported_features": 4}  # SUPPORT_SET_POSITION
        coordinator.hass.states.get.return_value = mock_cover_state

        # Set cover position and manually update history (simulating what _async_update_data does)
        actual_pos = await coordinator._set_cover_position("cover.test", 35, 4)
        if actual_pos is not None:
            coordinator._update_cover_position_history("cover.test", actual_pos)

        # Verify position history was updated
        history = coordinator._get_cover_position_history("cover.test")
        assert history == [35]

        # Set another position and update history
        actual_pos = await coordinator._set_cover_position("cover.test", 85, 4)
        if actual_pos is not None:
            coordinator._update_cover_position_history("cover.test", actual_pos)

        # Verify history tracks both positions
        history = coordinator._get_cover_position_history("cover.test")
        assert history == [85, 35]

    @pytest.mark.asyncio
    async def test_position_history_with_simulation_mode(self, mock_hass):
        """Test that position history works correctly in simulation mode."""
        from typing import cast

        from custom_components.smart_cover_automation.data import IntegrationConfigEntry
        from tests.conftest import MockConfigEntry, create_temperature_config

        # Create coordinator with simulation mode
        config = create_temperature_config()
        config["simulation_mode"] = True
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Mock cover state
        mock_hass.states.get = MagicMock()
        mock_cover_state = MagicMock()
        mock_cover_state.attributes = {"supported_features": 4}  # SUPPORT_SET_POSITION
        mock_hass.states.get.return_value = mock_cover_state

        # Set cover position in simulation mode and manually update history
        actual_pos = await coordinator._set_cover_position("cover.test", 65, 4)
        if actual_pos is not None:
            coordinator._update_cover_position_history("cover.test", actual_pos)

        # Verify position history is still updated even in simulation mode
        history = coordinator._get_cover_position_history("cover.test")
        assert history == [65]

    @pytest.mark.asyncio
    async def test_position_history_five_position_limit(self, coordinator: DataUpdateCoordinator):
        """Test that position history correctly maintains exactly COVER_POSITION_HISTORY_SIZE positions."""
        # Add exactly COVER_POSITION_HISTORY_SIZE positions
        positions = list(range(10, 10 + COVER_POSITION_HISTORY_SIZE * 10, 10))  # [10, 20, 30, ...] up to the limit
        for pos in positions:
            coordinator._update_cover_position_history("cover.test", pos)

        # Verify all positions are stored in newest-first order
        history = coordinator._get_cover_position_history("cover.test")
        expected_all = list(reversed(positions))  # Newest first
        assert history == expected_all

        # Add one more position - should drop the oldest
        new_position = positions[-1] + 10
        coordinator._update_cover_position_history("cover.test", new_position)
        history = coordinator._get_cover_position_history("cover.test")

        expected_all_after = [new_position] + list(reversed(positions[1:]))  # Drop oldest, add newest
        assert history == expected_all_after

        # Verify internal deque has exactly COVER_POSITION_HISTORY_SIZE elements
        assert len(coordinator._cover_position_history["cover.test"]) == COVER_POSITION_HISTORY_SIZE
