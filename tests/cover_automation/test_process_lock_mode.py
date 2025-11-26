"""Unit tests for CoverAutomation._process_lock_mode method.

This module comprehensively tests the lock mode processing logic:
- UNLOCKED mode behavior
- HOLD_POSITION mode behavior
- FORCE_OPEN mode behavior (already at position)
- FORCE_OPEN mode behavior (needs movement)
- FORCE_CLOSE mode behavior (already at position)
- FORCE_CLOSE mode behavior (needs movement)
- Cover attributes population
- Position history tracking
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.const import LockMode
from custom_components.smart_cover_automation.cover_automation import CoverAutomation


@pytest.fixture
def mock_resolved_config():
    """Create a mock resolved configuration."""
    resolved = MagicMock()
    resolved.covers_max_closure = 0
    resolved.covers_min_closure = 100
    resolved.sun_elevation_threshold = 10.0
    resolved.sun_azimuth_tolerance = 30.0
    resolved.manual_override_duration = 3600
    resolved.covers_min_position_delta = 5
    return resolved


@pytest.fixture
def mock_ha_interface():
    """Create a mock Home Assistant interface."""
    ha_interface = MagicMock()
    ha_interface.set_cover_position = AsyncMock(return_value=100)
    return ha_interface


@pytest.fixture
def mock_cover_pos_history_mgr():
    """Create a mock cover position history manager."""
    mgr = MagicMock()
    mgr.add = MagicMock()
    return mgr


@pytest.fixture
def basic_config():
    """Create a basic test configuration."""
    return {
        "cover.test_azimuth": 180.0,
    }


def create_cover_automation(
    lock_mode: LockMode,
    mock_resolved_config,
    basic_config,
    mock_cover_pos_history_mgr,
    mock_ha_interface,
) -> CoverAutomation:
    """Helper to create CoverAutomation with specific lock mode."""
    return CoverAutomation(
        entity_id="cover.test",
        resolved=mock_resolved_config,
        config=basic_config,
        cover_pos_history_mgr=mock_cover_pos_history_mgr,
        ha_interface=mock_ha_interface,
        lock_mode=lock_mode,
    )


class TestProcessLockModeUnlocked:
    """Test _process_lock_mode with UNLOCKED mode."""

    @pytest.mark.asyncio
    async def test_unlocked_returns_false(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test that UNLOCKED mode returns False (not locked)."""
        cover_auto = create_cover_automation(
            LockMode.UNLOCKED, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=50, features=0)

        assert locked is False
        assert cover_attrs == {}  # No attributes should be set
        mock_cover_pos_history_mgr.add.assert_not_called()
        mock_ha_interface.set_cover_position.assert_not_called()


class TestProcessLockModeHoldPosition:
    """Test _process_lock_mode with HOLD_POSITION mode."""

    @pytest.mark.asyncio
    async def test_hold_position_blocks_automation(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test that HOLD_POSITION blocks automation and returns True."""
        cover_auto = create_cover_automation(
            LockMode.HOLD_POSITION, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=42, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 42
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 42
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=42, cover_moved=False)
        mock_ha_interface.set_cover_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_hold_position_at_zero(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test HOLD_POSITION at fully closed position."""
        cover_auto = create_cover_automation(
            LockMode.HOLD_POSITION, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=0, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 0
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 0
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=0, cover_moved=False)

    @pytest.mark.asyncio
    async def test_hold_position_at_hundred(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test HOLD_POSITION at fully open position."""
        cover_auto = create_cover_automation(
            LockMode.HOLD_POSITION, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=100, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 100
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 100
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=100, cover_moved=False)


class TestProcessLockModeForceOpen:
    """Test _process_lock_mode with FORCE_OPEN mode."""

    @pytest.mark.asyncio
    async def test_force_open_already_at_target(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test FORCE_OPEN when cover is already fully open."""
        cover_auto = create_cover_automation(
            LockMode.FORCE_OPEN, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=100, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 100
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 100
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=100, cover_moved=False)
        mock_ha_interface.set_cover_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_open_needs_movement_from_closed(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
    ):
        """Test FORCE_OPEN when cover needs to move from closed."""
        mock_ha_interface.set_cover_position = AsyncMock(return_value=100)
        cover_auto = create_cover_automation(
            LockMode.FORCE_OPEN, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=0, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 100
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 100
        mock_ha_interface.set_cover_position.assert_called_once_with("cover.test", 100, 0)
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=100, cover_moved=True)

    @pytest.mark.asyncio
    async def test_force_open_needs_movement_from_partial(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
    ):
        """Test FORCE_OPEN when cover needs to move from partial position."""
        mock_ha_interface.set_cover_position = AsyncMock(return_value=100)
        cover_auto = create_cover_automation(
            LockMode.FORCE_OPEN, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=50, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 100
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 100
        mock_ha_interface.set_cover_position.assert_called_once_with("cover.test", 100, 0)
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=100, cover_moved=True)

    @pytest.mark.asyncio
    async def test_force_open_with_features(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test FORCE_OPEN passes features correctly."""
        mock_ha_interface.set_cover_position = AsyncMock(return_value=100)
        cover_auto = create_cover_automation(
            LockMode.FORCE_OPEN, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        features = 15  # Some feature flags
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=25, features=features)

        assert locked is True
        mock_ha_interface.set_cover_position.assert_called_once_with("cover.test", 100, features)


class TestProcessLockModeForceClose:
    """Test _process_lock_mode with FORCE_CLOSE mode."""

    @pytest.mark.asyncio
    async def test_force_close_already_at_target(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test FORCE_CLOSE when cover is already fully closed."""
        cover_auto = create_cover_automation(
            LockMode.FORCE_CLOSE, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=0, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 0
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 0
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=0, cover_moved=False)
        mock_ha_interface.set_cover_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_close_needs_movement_from_open(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
    ):
        """Test FORCE_CLOSE when cover needs to move from open."""
        mock_ha_interface.set_cover_position = AsyncMock(return_value=0)
        cover_auto = create_cover_automation(
            LockMode.FORCE_CLOSE, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=100, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 0
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 0
        mock_ha_interface.set_cover_position.assert_called_once_with("cover.test", 0, 0)
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=0, cover_moved=True)

    @pytest.mark.asyncio
    async def test_force_close_needs_movement_from_partial(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
    ):
        """Test FORCE_CLOSE when cover needs to move from partial position."""
        mock_ha_interface.set_cover_position = AsyncMock(return_value=0)
        cover_auto = create_cover_automation(
            LockMode.FORCE_CLOSE, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=75, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 0
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 0
        mock_ha_interface.set_cover_position.assert_called_once_with("cover.test", 0, 0)
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=0, cover_moved=True)

    @pytest.mark.asyncio
    async def test_force_close_with_features(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test FORCE_CLOSE passes features correctly."""
        mock_ha_interface.set_cover_position = AsyncMock(return_value=0)
        cover_auto = create_cover_automation(
            LockMode.FORCE_CLOSE, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        features = 31  # Some feature flags
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=88, features=features)

        assert locked is True
        mock_ha_interface.set_cover_position.assert_called_once_with("cover.test", 0, features)


class TestProcessLockModeEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_force_open_actual_position_differs(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
    ):
        """Test FORCE_OPEN when actual position differs from target (e.g., partial movement)."""
        # Simulate cover only reaching 95% instead of 100%
        mock_ha_interface.set_cover_position = AsyncMock(return_value=95)
        cover_auto = create_cover_automation(
            LockMode.FORCE_OPEN, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=0, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 95
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 95
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=95, cover_moved=True)

    @pytest.mark.asyncio
    async def test_force_close_actual_position_differs(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
    ):
        """Test FORCE_CLOSE when actual position differs from target."""
        # Simulate cover only reaching 5% instead of 0%
        mock_ha_interface.set_cover_position = AsyncMock(return_value=5)
        cover_auto = create_cover_automation(
            LockMode.FORCE_CLOSE, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=100, features=0)

        assert locked is True
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] == 5
        assert cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] == 5
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", new_position=5, cover_moved=True)

    @pytest.mark.asyncio
    async def test_empty_cover_attrs_dict(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test that method works with initially empty cover_attrs dict."""
        cover_auto = create_cover_automation(
            LockMode.HOLD_POSITION, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=50, features=0)

        assert locked is True
        assert len(cover_attrs) == 2  # Should have 2 keys added

    @pytest.mark.asyncio
    async def test_cover_attrs_with_existing_data(self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test that method preserves existing cover_attrs data."""
        cover_auto = create_cover_automation(
            LockMode.HOLD_POSITION, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
        )

        cover_attrs = {"existing_key": "existing_value", const.COVER_ATTR_COVER_AZIMUTH: 180}
        locked = await cover_auto._process_lock_mode(cover_attrs, current_pos=50, features=0)

        assert locked is True
        assert cover_attrs["existing_key"] == "existing_value"
        assert cover_attrs[const.COVER_ATTR_COVER_AZIMUTH] == 180
        assert const.COVER_ATTR_POS_TARGET_DESIRED in cover_attrs
        assert const.COVER_ATTR_POS_TARGET_FINAL in cover_attrs
