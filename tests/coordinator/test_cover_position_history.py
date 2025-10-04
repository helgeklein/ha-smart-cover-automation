"""Test position history tracking functionality in the coordinator."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.smart_cover_automation.const import (
    COVER_POSITION_HISTORY_SIZE,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.cover_position_history import (
    CoverPositionHistory,
    CoverPositionHistoryManager,
    PositionEntry,
)


class TestPositionHistory:
    """Test position history tracking functionality."""

    @pytest.mark.asyncio
    async def test_position_history_initialization(self, coordinator: DataUpdateCoordinator):
        """Test that position history starts empty."""
        # Initially empty position history - check via the getter method
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.non_existent")]
        assert history == []

        # Test getting history for non-existent cover
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.non_existent")]
        assert history == []

    @pytest.mark.asyncio
    async def test_position_history_single_update(self, coordinator: DataUpdateCoordinator):
        """Test position history with a single position update."""
        # Update position once
        coordinator._cover_pos_history_mgr.update("cover.test", 50)

        # Check history - first update should be current, no previous
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]
        assert history == [50]

        # Verify internal storage uses deque - check that it was initialized
        assert hasattr(coordinator._cover_pos_history_mgr, "_cover_position_history")
        assert "cover.test" in coordinator._cover_pos_history_mgr._cover_position_history
        assert list(coordinator._cover_pos_history_mgr._cover_position_history["cover.test"]) == [50]

    @pytest.mark.asyncio
    async def test_position_history_two_updates(self, coordinator: DataUpdateCoordinator):
        """Test position history with two position updates."""
        # Update position twice
        coordinator._cover_pos_history_mgr.update("cover.test", 30)
        coordinator._cover_pos_history_mgr.update("cover.test", 70)

        # Check history - should have current and previous
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]
        assert history == [70, 30]

        # Verify internal storage maintains newest first order - ensure it was initialized
        assert hasattr(coordinator._cover_pos_history_mgr, "_cover_position_history")
        assert list(coordinator._cover_pos_history_mgr._cover_position_history["cover.test"]) == [70, 30]

    @pytest.mark.asyncio
    async def test_position_history_multiple_updates(self, coordinator: DataUpdateCoordinator):
        """Test position history with multiple updates (uses COVER_POSITION_HISTORY_SIZE limit)."""
        # Update position multiple times - add more than the limit to test maxlen behavior
        positions = [10, 40, 80, 100, 60]
        for pos in positions:
            coordinator._cover_pos_history_mgr.update("cover.test", pos)

        # Check history - should keep last COVER_POSITION_HISTORY_SIZE positions in newest-first order
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]
        # Take last 3 positions: [80, 100, 60] and put in newest-first order: [60, 100, 80]
        expected_positions = [60, 100, 80]  # newest first order

        assert history == expected_positions

        # Verify internal storage - ensure it was initialized
        assert hasattr(coordinator._cover_pos_history_mgr, "_cover_position_history")
        assert list(coordinator._cover_pos_history_mgr._cover_position_history["cover.test"]) == expected_positions

        # Add one more to test maxlen behavior
        coordinator._cover_pos_history_mgr.update("cover.test", 20)
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]

        # Now we should have: [20, 60, 100] (newest first, 80 dropped)
        assert history == [20, 60, 100]

    @pytest.mark.asyncio
    async def test_position_history_multiple_covers(self, coordinator: DataUpdateCoordinator):
        """Test position history with multiple covers."""
        # Update positions for different covers
        coordinator._cover_pos_history_mgr.update("cover.test1", 25)
        coordinator._cover_pos_history_mgr.update("cover.test2", 75)
        coordinator._cover_pos_history_mgr.update("cover.test1", 50)

        # Check history for first cover
        history1 = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test1")]
        assert history1 == [50, 25]

        # Check history for second cover
        history2 = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test2")]
        assert history2 == [75]

        # Verify internal storage for each cover is independent
        assert list(coordinator._cover_pos_history_mgr._cover_position_history["cover.test1"]) == [50, 25]
        assert list(coordinator._cover_pos_history_mgr._cover_position_history["cover.test2"]) == [75]

    @pytest.mark.asyncio
    async def test_position_history_same_position_updates(self, coordinator: DataUpdateCoordinator):
        """Test position history when same position is set multiple times."""
        # Update with same position multiple times
        coordinator._cover_pos_history_mgr.update("cover.test", 60)
        coordinator._cover_pos_history_mgr.update("cover.test", 60)
        coordinator._cover_pos_history_mgr.update("cover.test", 60)

        # Should still track each update even if position is same
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]
        assert history == [60, 60, 60]

        # Verify internal storage
        assert list(coordinator._cover_pos_history_mgr._cover_position_history["cover.test"]) == [60, 60, 60]

    @pytest.mark.asyncio
    async def test_position_history_edge_case_positions(self, coordinator: DataUpdateCoordinator):
        """Test position history with edge case position values."""
        # Update with edge case positions
        coordinator._cover_pos_history_mgr.update("cover.test", 0)
        coordinator._cover_pos_history_mgr.update("cover.test", 100)

        # Check history
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]
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
            coordinator._cover_pos_history_mgr.update("cover.test", actual_pos)

        # Verify position history was updated
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]
        assert history == [35]

        # Set another position and update history
        actual_pos = await coordinator._set_cover_position("cover.test", 85, 4)
        if actual_pos is not None:
            coordinator._cover_pos_history_mgr.update("cover.test", actual_pos)

        # Verify history tracks both positions
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]
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
            coordinator._cover_pos_history_mgr.update("cover.test", actual_pos)

        # Verify position history is still updated even in simulation mode
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]
        assert history == [65]

    @pytest.mark.asyncio
    async def test_position_history_five_position_limit(self, coordinator: DataUpdateCoordinator):
        """Test that position history correctly maintains exactly COVER_POSITION_HISTORY_SIZE positions."""
        # Add exactly COVER_POSITION_HISTORY_SIZE positions
        positions = list(range(10, 10 + COVER_POSITION_HISTORY_SIZE * 10, 10))  # [10, 20, 30, ...] up to the limit
        for pos in positions:
            coordinator._cover_pos_history_mgr.update("cover.test", pos)

        # Verify all positions are stored in newest-first order
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]
        expected_all = list(reversed(positions))  # Newest first
        assert history == expected_all

        # Add one more position - should drop the oldest
        new_position = positions[-1] + 10
        coordinator._cover_pos_history_mgr.update("cover.test", new_position)
        history = [entry.position for entry in coordinator._cover_pos_history_mgr.get_entries("cover.test")]

        expected_all_after = [new_position] + list(reversed(positions[1:]))  # Drop oldest, add newest
        assert history == expected_all_after

    @pytest.mark.asyncio
    async def test_get_newest_position_empty_history(self, coordinator: DataUpdateCoordinator):
        """Test getting newest position when no history exists."""
        # Should return None for cover that has no history
        newest_entry = coordinator._cover_pos_history_mgr.get_latest_entry("cover.nonexistent")
        newest = newest_entry.position if newest_entry else None
        assert newest is None

    @pytest.mark.asyncio
    async def test_get_newest_position_single_entry(self, coordinator: DataUpdateCoordinator):
        """Test getting newest position with single history entry."""
        # Add one position
        coordinator._cover_pos_history_mgr.update("cover.test", 75)

        # Should return that position
        newest_entry = coordinator._cover_pos_history_mgr.get_latest_entry("cover.test")
        newest = newest_entry.position if newest_entry else None
        assert newest == 75

    @pytest.mark.asyncio
    async def test_get_newest_position_multiple_entries(self, coordinator: DataUpdateCoordinator):
        """Test getting newest position with multiple history entries."""
        # Add multiple positions
        coordinator._cover_pos_history_mgr.update("cover.test", 25)
        coordinator._cover_pos_history_mgr.update("cover.test", 50)
        coordinator._cover_pos_history_mgr.update("cover.test", 90)

        # Should return the most recent one (90)
        newest_entry = coordinator._cover_pos_history_mgr.get_latest_entry("cover.test")
        newest = newest_entry.position if newest_entry else None
        assert newest == 90


class TestPositionEntryAndTimestamps:
    """Test new timestamp functionality in position history."""

    def test_position_entry_creation(self):
        """Test PositionEntry dataclass creation and properties."""
        # Create a test timestamp
        test_time = datetime(2025, 10, 4, 12, 0, 0, tzinfo=timezone.utc)

        # Test with valid position
        entry = PositionEntry(position=50, timestamp=test_time)
        assert entry.position == 50
        assert entry.timestamp == test_time

        # Test with None position
        entry_none = PositionEntry(position=None, timestamp=test_time)
        assert entry_none.position is None
        assert entry_none.timestamp == test_time

    def test_cover_position_history_add_with_explicit_timestamp(self):
        """Test adding positions with explicit timestamps."""
        history = CoverPositionHistory()

        # Create test timestamps in chronological order
        time1 = datetime(2025, 10, 4, 10, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 10, 4, 11, 0, 0, tzinfo=timezone.utc)
        time3 = datetime(2025, 10, 4, 12, 0, 0, tzinfo=timezone.utc)

        # Add positions with explicit timestamps
        history.add_position(30, time1)
        history.add_position(60, time2)
        history.add_position(90, time3)

        # Check that positions are in newest-first order
        assert history.get_all() == [90, 60, 30]

        # Check that timestamps are properly stored
        entries = history.get_all_entries()
        assert len(entries) == 3
        assert entries[0].position == 90
        assert entries[0].timestamp == time3
        assert entries[1].position == 60
        assert entries[1].timestamp == time2
        assert entries[2].position == 30
        assert entries[2].timestamp == time1

    def test_cover_position_history_add_with_auto_timestamp(self):
        """Test adding positions with automatic timestamp generation."""
        history = CoverPositionHistory()

        # Get time before adding position
        before_time = datetime.now(timezone.utc)

        # Add position without explicit timestamp
        history.add_position(75)

        # Get time after adding position
        after_time = datetime.now(timezone.utc)

        # Verify position was added correctly
        entry = history.get_newest_entry()
        assert entry and entry.position == 75

        # Verify timestamp was automatically generated within reasonable bounds
        entry = history.get_newest_entry()
        assert entry is not None
        assert entry.position == 75
        assert before_time <= entry.timestamp <= after_time

    def test_cover_position_history_get_newest_entry(self):
        """Test getting newest entry with timestamp."""
        history = CoverPositionHistory()

        # Test empty history
        assert history.get_newest_entry() is None

        # Add some positions with timestamps
        time1 = datetime(2025, 10, 4, 10, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 10, 4, 11, 0, 0, tzinfo=timezone.utc)

        history.add_position(40, time1)
        history.add_position(80, time2)

        # Get newest entry
        newest = history.get_newest_entry()
        assert newest is not None
        assert newest.position == 80
        assert newest.timestamp == time2

    def test_cover_position_history_get_all_entries(self):
        """Test getting all entries with timestamps."""
        history = CoverPositionHistory()

        # Test empty history
        assert history.get_all_entries() == []

        # Add positions with timestamps
        time1 = datetime(2025, 10, 4, 9, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 10, 4, 11, 0, 0, tzinfo=timezone.utc)

        history.add_position(25, time1)
        history.add_position(75, time2)

        # Get all entries
        entries = history.get_all_entries()
        assert len(entries) == 2

        # Verify order (newest first)
        assert entries[0].position == 75
        assert entries[0].timestamp == time2
        assert entries[1].position == 25
        assert entries[1].timestamp == time1

    def test_cover_position_history_backward_compatibility(self):
        """Test that existing methods still work correctly with new timestamp functionality."""
        history = CoverPositionHistory()

        # Add positions using new timestamp feature
        time1 = datetime(2025, 10, 4, 10, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 10, 4, 11, 0, 0, tzinfo=timezone.utc)

        history.add_position(35, time1)
        history.add_position(65, time2)

        # Test that old methods still work
        entry = history.get_newest_entry()
        assert entry and entry.position == 65
        assert history.get_all() == [65, 35]
        assert len(history) == 2
        assert bool(history) is True
        assert list(history) == [65, 35]

    def test_position_history_manager_update_with_timestamp(self):
        """Test manager update method with explicit timestamps."""
        manager = CoverPositionHistoryManager()

        # Create test timestamps
        time1 = datetime(2025, 10, 4, 14, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 10, 4, 15, 0, 0, tzinfo=timezone.utc)

        # Update with explicit timestamps
        manager.update("cover.test", 45, time1)
        manager.update("cover.test", 85, time2)

        # Verify positions were stored correctly
        assert [entry.position for entry in manager.get_entries("cover.test")] == [85, 45]

        # Verify timestamps were stored correctly
        entries = manager.get_entries("cover.test")
        assert len(entries) == 2
        assert entries[0].position == 85
        assert entries[0].timestamp == time2
        assert entries[1].position == 45
        assert entries[1].timestamp == time1

    def test_position_history_manager_update_auto_timestamp(self):
        """Test manager update method with automatic timestamp generation."""
        manager = CoverPositionHistoryManager()

        # Get time before update
        before_time = datetime.now(timezone.utc)

        # Update without explicit timestamp
        manager.update("cover.test", 55)

        # Get time after update
        after_time = datetime.now(timezone.utc)

        # Verify position was stored
        latest_entry = manager.get_latest_entry("cover.test")
        assert latest_entry and latest_entry.position == 55

        # Verify timestamp was automatically generated
        entry = manager.get_latest_entry("cover.test")
        assert entry is not None
        assert entry.position == 55
        assert before_time <= entry.timestamp <= after_time

    def test_position_history_manager_get_entries(self):
        """Test manager get_entries method."""
        manager = CoverPositionHistoryManager()

        # Test non-existent cover
        assert manager.get_entries("cover.nonexistent") == []

        # Add some positions
        time1 = datetime(2025, 10, 4, 16, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 10, 4, 17, 0, 0, tzinfo=timezone.utc)
        time3 = datetime(2025, 10, 4, 18, 0, 0, tzinfo=timezone.utc)

        manager.update("cover.test", 20, time1)
        manager.update("cover.test", 50, time2)
        manager.update("cover.test", 80, time3)

        # Get entries
        entries = manager.get_entries("cover.test")
        assert len(entries) == 3

        # Verify order and content
        assert entries[0].position == 80
        assert entries[0].timestamp == time3
        assert entries[1].position == 50
        assert entries[1].timestamp == time2
        assert entries[2].position == 20
        assert entries[2].timestamp == time1

    def test_position_history_manager_get_latest_entry(self):
        """Test manager get_latest_entry method."""
        manager = CoverPositionHistoryManager()

        # Test non-existent cover
        assert manager.get_latest_entry("cover.nonexistent") is None

        # Add positions
        time1 = datetime(2025, 10, 4, 19, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 10, 4, 20, 0, 0, tzinfo=timezone.utc)

        manager.update("cover.test", 30, time1)
        manager.update("cover.test", 70, time2)

        # Get latest entry
        latest = manager.get_latest_entry("cover.test")
        assert latest is not None
        assert latest.position == 70
        assert latest.timestamp == time2

    def test_position_history_manager_backward_compatibility(self):
        """Test that manager's existing methods work correctly with new functionality."""
        manager = CoverPositionHistoryManager()

        # Add positions using new timestamp feature
        time1 = datetime(2025, 10, 4, 21, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 10, 4, 22, 0, 0, tzinfo=timezone.utc)

        manager.update("cover.test", 40, time1)
        manager.update("cover.test", 90, time2)

        # Test that existing methods still work
        assert [entry.position for entry in manager.get_entries("cover.test")] == [90, 40]
        latest_entry = manager.get_latest_entry("cover.test")
        assert latest_entry and latest_entry.position == 90

    def test_position_history_with_none_positions_and_timestamps(self):
        """Test handling of None positions with timestamps."""
        manager = CoverPositionHistoryManager()

        # Create timestamps
        time1 = datetime(2025, 10, 4, 23, 0, 0, tzinfo=timezone.utc)
        time2 = datetime(2025, 10, 5, 0, 0, 0, tzinfo=timezone.utc)

        # Add positions including None
        manager.update("cover.test", 60, time1)
        manager.update("cover.test", 80, time2)

        # Verify positions
        assert [entry.position for entry in manager.get_entries("cover.test")] == [80, 60]
        latest_entry = manager.get_latest_entry("cover.test")
        assert latest_entry and latest_entry.position == 80

        # Verify timestamps
        entries = manager.get_entries("cover.test")
        assert len(entries) == 2
        assert entries[0].position == 80
        assert entries[0].timestamp == time2
        assert entries[1].position == 60
        assert entries[1].timestamp == time1

    def test_position_history_size_limit_with_timestamps(self):
        """Test that size limit works correctly with timestamped entries."""
        manager = CoverPositionHistoryManager()

        # Add more positions than the limit
        base_time = datetime(2025, 10, 4, 12, 0, 0, tzinfo=timezone.utc)

        for i in range(COVER_POSITION_HISTORY_SIZE + 3):
            timestamp = base_time.replace(minute=i)
            manager.update("cover.test", i * 10, timestamp)

        # Verify size limit is respected
        entries = manager.get_entries("cover.test")
        assert len(entries) == COVER_POSITION_HISTORY_SIZE

        # Verify newest entries are kept (should have the highest position values)
        expected_newest_positions = [(COVER_POSITION_HISTORY_SIZE + 2 - i) * 10 for i in range(COVER_POSITION_HISTORY_SIZE)]
        actual_positions = [entry.position for entry in entries]
        assert actual_positions == expected_newest_positions
