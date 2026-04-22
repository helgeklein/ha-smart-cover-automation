"""Comprehensive unit tests for the CoverAutomation class.

This module tests CoverAutomation in isolation, focusing on:
- Initialization
- Cover azimuth validation
- Cover state validation
- Cover movement detection
- Manual override detection
- Sun hitting calculations
- Desired position calculations
- Lockout protection
- Cover movement logic
- Logging functionality
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import (
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.const import LockMode, ReopeningMode, TiltMode
from custom_components.smart_cover_automation.cover_automation import (
    CoverAutomation,
    CoverMovementReason,
)
from custom_components.smart_cover_automation.cover_automation import (
    SensorData as CoverSensorData,
)
from custom_components.smart_cover_automation.cover_position_history import PositionEntry, RecentAutomationAction


def make_sensor_data(*, temp_min: float = 18.0, **kwargs):
    """Create sensor data with a default daily minimum temperature for tests."""

    return CoverSensorData(temp_min=temp_min, **kwargs)


@pytest.fixture
def mock_resolved_config():
    """Create a mock resolved configuration."""
    resolved = MagicMock()
    resolved.covers_max_closure = 0
    resolved.covers_min_closure = 100
    resolved.evening_closure_max_closure = 0
    resolved.sun_elevation_threshold = 10.0
    resolved.sun_azimuth_tolerance = 30.0
    resolved.manual_override_duration = 3600
    resolved.evening_closure_ignore_manual_override_duration = False
    resolved.evening_closure_keep_closed = False
    resolved.evening_closure_cover_list = ()
    resolved.automatic_reopening_mode = ReopeningMode.ACTIVE
    resolved.covers_min_position_delta = 5
    resolved.tilt_mode_day = TiltMode.AUTO
    resolved.tilt_open_to_cover_open_delay = 0
    return resolved


@pytest.fixture
def mock_ha_interface():
    """Create a mock Home Assistant interface."""
    ha_interface = MagicMock()
    ha_interface.get_entity_state = MagicMock(return_value=None)
    ha_interface.set_cover_position = AsyncMock(return_value=50)
    ha_interface.add_logbook_entry = AsyncMock()
    return ha_interface


@pytest.fixture
def mock_cover_pos_history_mgr():
    """Create a mock cover position history manager."""
    mgr = MagicMock()
    mgr.get_latest_entry = MagicMock(return_value=None)
    mgr.get_recent_automation_action = MagicMock(return_value=None)
    mgr.set_recent_automation_action = MagicMock()
    mgr.clear_recent_automation_action = MagicMock()
    mgr.mark_closed_by_automation = MagicMock()
    mgr.clear_closed_by_automation = MagicMock()
    mgr.set_delayed_reopen_action = MagicMock()
    mgr.get_delayed_reopen_action = MagicMock(return_value=None)
    mgr.clear_delayed_reopen_action = MagicMock()
    mgr.was_closed_by_automation = MagicMock(return_value=False)
    mgr.get_closed_by_automation_reason = MagicMock(return_value=None)
    mgr.mark_manual_override_blocked = MagicMock()
    mgr.clear_manual_override_blocked = MagicMock()
    mgr.was_manual_override_blocking = MagicMock(return_value=False)
    mgr.add = MagicMock()
    mgr.get_entries = MagicMock(return_value=[])
    return mgr


@pytest.fixture
def basic_config():
    """Create a basic test configuration."""
    return {
        "cover.test_cover_azimuth": 180.0,
    }


@pytest.fixture
def cover_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger):
    """Create a CoverAutomation instance for testing."""
    # Ensure lock mode is unlocked for these tests
    mock_resolved_config.lock_mode = LockMode.UNLOCKED
    return CoverAutomation(
        entity_id="cover.test",
        resolved=mock_resolved_config,
        config=basic_config,
        cover_pos_history_mgr=mock_cover_pos_history_mgr,
        ha_interface=mock_ha_interface,
        logger=mock_logger,
    )


@pytest.fixture
def sensor_data():
    """Create sample sensor data."""
    return make_sensor_data(
        sun_azimuth=180.0,
        sun_elevation=45.0,
        temp_max=30.0,
        temp_hot=True,
        weather_condition="sunny",
        weather_sunny=True,
        evening_closure=False,
        post_evening_closure=False,
    )


@pytest.fixture
def mock_state():
    """Create a mock cover state."""
    state = MagicMock()
    state.state = STATE_OPEN
    state.attributes = {
        ATTR_CURRENT_POSITION: 100,
        "supported_features": CoverEntityFeature.SET_POSITION,
    }
    return state


class TestCoverAutomationInitialization:
    """Test CoverAutomation initialization."""

    def test_initialization_with_valid_config(self, cover_automation, basic_config):
        """Test that CoverAutomation initializes correctly with valid configuration."""
        assert cover_automation.entity_id == "cover.test"
        assert cover_automation.config == basic_config
        assert cover_automation.resolved is not None
        assert cover_automation._cover_pos_history_mgr is not None
        assert cover_automation._ha_interface is not None

    def test_initialization_stores_all_dependencies(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger
    ):
        """Test that all dependencies are stored correctly."""
        cover_auto = CoverAutomation(
            entity_id="cover.living_room",
            resolved=mock_resolved_config,
            config=basic_config,
            cover_pos_history_mgr=mock_cover_pos_history_mgr,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )

        assert cover_auto.entity_id == "cover.living_room"
        assert cover_auto.resolved == mock_resolved_config
        assert cover_auto.config == basic_config
        assert cover_auto._cover_pos_history_mgr == mock_cover_pos_history_mgr
        assert cover_auto._ha_interface == mock_ha_interface


class TestGetCoverAzimuth:
    """Test _get_cover_azimuth method."""

    def test_get_cover_azimuth_valid(self, cover_automation):
        """Test getting valid cover azimuth."""
        azimuth = cover_automation._get_cover_azimuth()
        assert azimuth == 180.0

    def test_get_cover_azimuth_missing(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger):
        """Test handling missing cover azimuth."""
        config = {}  # No azimuth configured
        cover_auto = CoverAutomation(
            entity_id="cover.test",
            resolved=mock_resolved_config,
            config=config,
            cover_pos_history_mgr=mock_cover_pos_history_mgr,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        azimuth = cover_auto._get_cover_azimuth()
        assert azimuth is None

    def test_get_cover_azimuth_invalid_type(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger):
        """Test handling invalid cover azimuth type."""
        config = {"cover.test_cover_azimuth": "invalid"}
        cover_auto = CoverAutomation(
            entity_id="cover.test",
            resolved=mock_resolved_config,
            config=config,
            cover_pos_history_mgr=mock_cover_pos_history_mgr,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        azimuth = cover_auto._get_cover_azimuth()
        assert azimuth is None

    def test_get_cover_azimuth_zero(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger):
        """Test cover azimuth of zero (North)."""
        config = {"cover.test_cover_azimuth": 0.0}
        cover_auto = CoverAutomation(
            entity_id="cover.test",
            resolved=mock_resolved_config,
            config=config,
            cover_pos_history_mgr=mock_cover_pos_history_mgr,
            ha_interface=mock_ha_interface,
            logger=mock_logger,
        )
        azimuth = cover_auto._get_cover_azimuth()
        assert azimuth == 0.0


class TestValidateCoverState:
    """Test _validate_cover_state method."""

    def test_validate_cover_state_valid(self, cover_automation, mock_state):
        """Test validation of valid cover state."""
        result = cover_automation._validate_cover_state(mock_state)
        assert result is True

    def test_validate_cover_state_none(self, cover_automation):
        """Test validation when state is None."""
        result = cover_automation._validate_cover_state(None)
        assert result is False

    def test_validate_cover_state_none_state_value(self, cover_automation):
        """Test validation when state.state is None."""
        state = MagicMock()
        state.state = None
        result = cover_automation._validate_cover_state(state)
        assert result is False

    def test_validate_cover_state_empty_string(self, cover_automation):
        """Test validation when state is empty string."""
        state = MagicMock()
        state.state = ""
        result = cover_automation._validate_cover_state(state)
        assert result is False

    def test_validate_cover_state_unavailable(self, cover_automation):
        """Test validation when state is unavailable."""
        state = MagicMock()
        state.state = STATE_UNAVAILABLE
        result = cover_automation._validate_cover_state(state)
        assert result is False

    def test_validate_cover_state_unknown(self, cover_automation):
        """Test validation when state is unknown."""
        state = MagicMock()
        state.state = STATE_UNKNOWN
        result = cover_automation._validate_cover_state(state)
        assert result is False


class TestIsCoverMoving:
    """Test _is_cover_moving method."""

    def test_is_cover_moving_opening(self, cover_automation):
        """Test detection of opening cover."""
        state = MagicMock()
        state.state = STATE_OPENING
        result = cover_automation._is_cover_moving(state)
        assert result is True

    def test_is_cover_moving_closing(self, cover_automation):
        """Test detection of closing cover."""
        state = MagicMock()
        state.state = STATE_CLOSING
        result = cover_automation._is_cover_moving(state)
        assert result is True

    def test_is_cover_moving_open(self, cover_automation):
        """Test detection when cover is open (not moving)."""
        state = MagicMock()
        state.state = STATE_OPEN
        result = cover_automation._is_cover_moving(state)
        assert result is False

    def test_is_cover_moving_closed(self, cover_automation):
        """Test detection when cover is closed (not moving)."""
        state = MagicMock()
        state.state = STATE_CLOSED
        result = cover_automation._is_cover_moving(state)
        assert result is False

    def test_is_cover_moving_case_insensitive(self, cover_automation):
        """Test that state check is case insensitive."""
        state = MagicMock()
        state.state = "OPENING"
        result = cover_automation._is_cover_moving(state)
        assert result is True


class TestGetCoverPosition:
    """Test _get_cover_position method."""

    def test_get_cover_position_with_set_position_feature(self, cover_automation):
        """Test getting position from cover that supports SET_POSITION."""
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: 75}
        features = CoverEntityFeature.SET_POSITION

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 75

    def test_get_cover_position_with_set_position_feature_zero(self, cover_automation):
        """Test getting position 0 (fully closed)."""
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: 0}
        features = CoverEntityFeature.SET_POSITION

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 0

    def test_get_cover_position_with_set_position_feature_hundred(self, cover_automation):
        """Test getting position 100 (fully open)."""
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: 100}
        features = CoverEntityFeature.SET_POSITION

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 100

    def test_get_cover_position_missing_attribute(self, cover_automation):
        """Test handling missing position attribute when feature is supported."""
        state = MagicMock()
        state.attributes = {}  # No position attribute
        features = CoverEntityFeature.SET_POSITION

        success, position = cover_automation._get_cover_position(state, features)
        assert success is False
        assert position == 100  # Default to fully open

    def test_get_cover_position_none_attribute(self, cover_automation):
        """Test handling None position attribute."""
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: None}
        features = CoverEntityFeature.SET_POSITION

        success, position = cover_automation._get_cover_position(state, features)
        assert success is False
        assert position == 100

    def test_get_cover_position_invalid_attribute_type(self, cover_automation):
        """Test handling invalid position attribute type."""
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: "invalid"}
        features = CoverEntityFeature.SET_POSITION

        success, position = cover_automation._get_cover_position(state, features)
        assert success is False
        assert position == 100

    def test_get_cover_position_binary_cover_open(self, cover_automation):
        """Test binary cover (no SET_POSITION) in open state."""
        state = MagicMock()
        state.state = STATE_OPEN
        features = 0  # No SET_POSITION feature

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 100

    def test_get_cover_position_binary_cover_closed(self, cover_automation):
        """Test binary cover in closed state."""
        state = MagicMock()
        state.state = STATE_CLOSED
        features = 0

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 0

    def test_get_cover_position_binary_cover_opening(self, cover_automation):
        """Test binary cover in opening state (transitional)."""
        state = MagicMock()
        state.state = STATE_OPENING
        features = 0

        success, position = cover_automation._get_cover_position(state, features)
        assert success is False
        assert position == 100  # Unknown state defaults to open

    def test_get_cover_position_binary_cover_closing(self, cover_automation):
        """Test binary cover in closing state (transitional)."""
        state = MagicMock()
        state.state = STATE_CLOSING
        features = 0

        success, position = cover_automation._get_cover_position(state, features)
        assert success is False
        assert position == 100

    def test_get_cover_position_binary_cover_unknown_state(self, cover_automation):
        """Test binary cover with unknown state."""
        state = MagicMock()
        state.state = "weird_state"
        features = 0

        success, position = cover_automation._get_cover_position(state, features)
        assert success is False
        assert position == 100

    def test_get_cover_position_binary_cover_none_state(self, cover_automation):
        """Test binary cover with None state."""
        state = MagicMock()
        state.state = None
        features = 0

        success, position = cover_automation._get_cover_position(state, features)
        assert success is False
        assert position == 100

    def test_get_cover_position_binary_cover_case_insensitive(self, cover_automation):
        """Test binary cover state checking is case insensitive."""
        state = MagicMock()
        state.state = "OPEN"
        features = 0

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 100

    def test_get_cover_position_float_conversion(self, cover_automation):
        """Test that float position values are converted to int."""
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: 75.7}
        features = CoverEntityFeature.SET_POSITION

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 75

    def test_get_cover_position_edge_case_over_100(self, cover_automation):
        """Test handling position value over 100."""
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: 150}
        features = CoverEntityFeature.SET_POSITION

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 150  # Returns actual value, clamping happens elsewhere

    def test_get_cover_position_edge_case_negative(self, cover_automation):
        """Test handling negative position value."""
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: -10}
        features = CoverEntityFeature.SET_POSITION

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == -10  # Returns actual value, clamping happens elsewhere

    def test_get_cover_position_mixed_features(self, cover_automation):
        """Test cover with multiple features including SET_POSITION."""
        state = MagicMock()
        state.attributes = {ATTR_CURRENT_POSITION: 50}
        features = CoverEntityFeature.SET_POSITION | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 50

    def test_get_cover_position_no_features_open_state(self, cover_automation):
        """Test cover with no features advertised but open state."""
        state = MagicMock()
        state.state = STATE_OPEN
        features = 0

        success, position = cover_automation._get_cover_position(state, features)
        assert success is True
        assert position == 100

    def test_get_cover_position_exception_handling_with_state_access(self, cover_automation):
        """Test exception handling when state access raises exception."""
        state = MagicMock()
        state.state = MagicMock(side_effect=AttributeError("No state"))
        state.attributes = {}
        features = 0  # Binary cover

        success, position = cover_automation._get_cover_position(state, features)
        assert success is False
        assert position == 100  # Defaults to fully open

    def test_get_cover_position_exception_handling_type_error(self, cover_automation):
        """Test exception handling when state access raises TypeError."""
        state = MagicMock()
        state.state = MagicMock(side_effect=TypeError("Invalid state"))
        state.attributes = {}
        features = 0  # Binary cover

        success, position = cover_automation._get_cover_position(state, features)
        assert success is False
        assert position == 100  # Defaults to fully open


class TestCheckManualOverride:
    """Test _check_manual_override method."""

    def test_get_manual_override_remaining_active(self, cover_automation, mock_cover_pos_history_mgr, mock_resolved_config):
        """Test remaining override time when manual override is active."""
        mock_resolved_config.manual_override_duration = 3600
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) - timedelta(seconds=100), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry

        remaining = cover_automation._get_manual_override_remaining(75)

        assert remaining is not None
        assert 3498 <= remaining <= 3500

    def test_check_manual_override_no_history(self, cover_automation, mock_cover_pos_history_mgr):
        """Test when there's no position history."""
        mock_cover_pos_history_mgr.get_latest_entry.return_value = None
        result = cover_automation._check_manual_override(50)
        assert result is False

    def test_check_manual_override_position_unchanged(self, cover_automation, mock_cover_pos_history_mgr):
        """Test when position hasn't changed."""
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) - timedelta(seconds=100), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry
        result = cover_automation._check_manual_override(50)
        assert result is False

    def test_check_manual_override_active(self, cover_automation, mock_cover_pos_history_mgr, mock_resolved_config):
        """Test when manual override is active."""
        mock_resolved_config.manual_override_duration = 3600
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) - timedelta(seconds=100), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry
        result = cover_automation._check_manual_override(75)  # Position changed
        assert result is True

    def test_get_manual_override_remaining_ignores_expected_recent_automation_drift(
        self, cover_automation, mock_cover_pos_history_mgr, mock_resolved_config
    ):
        """Expected recent automation drift should not activate manual override."""

        mock_resolved_config.manual_override_duration = 3600
        mock_resolved_config.covers_min_position_delta = 5
        entry = PositionEntry(position=0, timestamp=datetime.now(timezone.utc) - timedelta(seconds=30), cover_moved=True)
        recent_automation_action = RecentAutomationAction(
            expected_position=0,
            allowed_position_drift=mock_resolved_config.covers_min_position_delta,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
        )
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry
        mock_cover_pos_history_mgr.get_recent_automation_action.return_value = recent_automation_action

        remaining = cover_automation._get_manual_override_remaining(2)

        assert remaining is None
        mock_cover_pos_history_mgr.add.assert_called_once()
        mock_cover_pos_history_mgr.clear_recent_automation_action.assert_not_called()

    def test_get_manual_override_remaining_keeps_manual_override_for_large_recent_automation_drift(
        self, cover_automation, mock_cover_pos_history_mgr, mock_resolved_config
    ):
        """Large movement after recent automation should still count as manual override."""

        mock_resolved_config.manual_override_duration = 3600
        mock_resolved_config.covers_min_position_delta = 5
        entry = PositionEntry(position=0, timestamp=datetime.now(timezone.utc) - timedelta(seconds=30), cover_moved=True)
        recent_automation_action = RecentAutomationAction(
            expected_position=0,
            allowed_position_drift=mock_resolved_config.covers_min_position_delta,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
        )
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry
        mock_cover_pos_history_mgr.get_recent_automation_action.return_value = recent_automation_action

        remaining = cover_automation._get_manual_override_remaining(12)

        assert remaining is not None
        mock_cover_pos_history_mgr.clear_recent_automation_action.assert_called_once_with("cover.test")

    def test_check_manual_override_expired(self, cover_automation, mock_cover_pos_history_mgr, mock_resolved_config):
        """Test when manual override has expired."""
        mock_resolved_config.manual_override_duration = 3600
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) - timedelta(seconds=3700), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry
        result = cover_automation._check_manual_override(75)  # Position changed but expired
        assert result is False

    def test_check_manual_override_future_timestamp(self, cover_automation, mock_cover_pos_history_mgr):
        """Test handling of future timestamp (system time change)."""
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) + timedelta(seconds=100), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry
        result = cover_automation._check_manual_override(75)
        assert result is False

    def test_should_ignore_manual_override_for_evening_closure(self, cover_automation, sensor_data, mock_resolved_config):
        """Test bypass applies to covers in the evening closure list."""
        mock_resolved_config.evening_closure_ignore_manual_override_duration = True
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        sensor_data.evening_closure = True

        result = cover_automation._should_ignore_manual_override(sensor_data)

        assert result is True

    def test_should_not_ignore_manual_override_for_other_covers(self, cover_automation, sensor_data, mock_resolved_config):
        """Test bypass does not apply to covers outside the evening closure list."""
        mock_resolved_config.evening_closure_ignore_manual_override_duration = True
        mock_resolved_config.evening_closure_cover_list = ("cover.other",)
        sensor_data.evening_closure = True

        result = cover_automation._should_ignore_manual_override(sensor_data)

        assert result is False

    def test_should_not_ignore_manual_override_during_post_evening_closure_keep_closed(
        self, cover_automation, sensor_data, mock_resolved_config
    ):
        """Test the sunset-only bypass does not extend into overnight keep-closed mode."""
        mock_resolved_config.evening_closure_ignore_manual_override_duration = True
        mock_resolved_config.evening_closure_keep_closed = True
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        sensor_data.evening_closure = False
        sensor_data.post_evening_closure = True

        result = cover_automation._should_ignore_manual_override(sensor_data)

        assert result is False

    async def test_process_clears_automation_closed_marker_on_manual_override(
        self,
        cover_automation,
        mock_cover_pos_history_mgr,
        mock_state,
        sensor_data,
    ):
        """Manual override should clear passive reopening eligibility."""

        entry = PositionEntry(position=0, timestamp=datetime.now(timezone.utc) - timedelta(seconds=30), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry
        mock_state.attributes[ATTR_CURRENT_POSITION] = 50

        await cover_automation.process(mock_state, sensor_data)

        mock_cover_pos_history_mgr.clear_closed_by_automation.assert_called_once_with("cover.test")

    def test_get_evening_closure_movement_reason_for_keep_closed(self, cover_automation, sensor_data, mock_resolved_config):
        """Test overnight keep-closed maps to its dedicated evening movement reason."""
        mock_resolved_config.evening_closure_keep_closed = True
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        sensor_data.post_evening_closure = True

        result = cover_automation._get_evening_closure_movement_reason(sensor_data)

        assert result == CoverMovementReason.CLOSING_KEEP_CLOSED_AFTER_EVENING_CLOSURE


class TestCalculateSunHitting:
    """Test _calculate_sun_hitting method."""

    def test_calculate_sun_hitting_direct_hit(self, cover_automation, mock_resolved_config):
        """Test when sun is directly hitting the window."""
        mock_resolved_config.sun_elevation_threshold = 10.0
        mock_resolved_config.sun_azimuth_tolerance = 30.0

        sun_hitting, diff = cover_automation._calculate_sun_hitting(sun_azimuth=180.0, sun_elevation=45.0, cover_azimuth=180.0)
        assert sun_hitting is True
        assert diff == 0.0

    def test_calculate_sun_hitting_within_tolerance(self, cover_automation, mock_resolved_config):
        """Test when sun is within azimuth tolerance."""
        mock_resolved_config.sun_elevation_threshold = 10.0
        mock_resolved_config.sun_azimuth_tolerance = 30.0

        sun_hitting, diff = cover_automation._calculate_sun_hitting(sun_azimuth=200.0, sun_elevation=45.0, cover_azimuth=180.0)
        assert sun_hitting is True
        assert diff == 20.0

    def test_calculate_sun_hitting_outside_tolerance(self, cover_automation, mock_resolved_config):
        """Test when sun is outside azimuth tolerance."""
        mock_resolved_config.sun_elevation_threshold = 10.0
        mock_resolved_config.sun_azimuth_tolerance = 30.0

        sun_hitting, diff = cover_automation._calculate_sun_hitting(sun_azimuth=250.0, sun_elevation=45.0, cover_azimuth=180.0)
        assert sun_hitting is False
        assert diff == 70.0

    def test_calculate_sun_hitting_low_elevation(self, cover_automation, mock_resolved_config):
        """Test when sun elevation is below threshold."""
        mock_resolved_config.sun_elevation_threshold = 10.0
        mock_resolved_config.sun_azimuth_tolerance = 30.0

        sun_hitting, diff = cover_automation._calculate_sun_hitting(sun_azimuth=180.0, sun_elevation=5.0, cover_azimuth=180.0)
        assert sun_hitting is False
        assert diff == 0.0


class TestCalculateAngleDifference:
    """Test _calculate_angle_difference static method."""

    def test_calculate_angle_difference_same_angle(self):
        """Test difference between same angles."""
        diff = CoverAutomation._calculate_angle_difference(180.0, 180.0)
        assert diff == 0.0

    def test_calculate_angle_difference_standard(self):
        """Test standard angle difference."""
        diff = CoverAutomation._calculate_angle_difference(180.0, 135.0)
        assert diff == 45.0

    def test_calculate_angle_difference_wraparound(self):
        """Test angle difference with wraparound."""
        diff = CoverAutomation._calculate_angle_difference(0.0, 350.0)
        assert diff == 10.0

    def test_calculate_angle_difference_reverse_wraparound(self):
        """Test angle difference with reverse wraparound."""
        diff = CoverAutomation._calculate_angle_difference(350.0, 0.0)
        assert diff == 10.0

    def test_calculate_angle_difference_maximum(self):
        """Test maximum angle difference."""
        diff = CoverAutomation._calculate_angle_difference(0.0, 180.0)
        assert diff == 180.0

    def test_calculate_angle_difference_over_360(self):
        """Test angle difference with angles over 360."""
        diff = CoverAutomation._calculate_angle_difference(450.0, 90.0)
        assert diff == 0.0  # 450 % 360 = 90


class TestCalculateDesiredPosition:
    """Test _calculate_desired_position method."""

    def test_calculate_desired_position_heat_protection(self, cover_automation, mock_resolved_config):
        """Test desired position for heat protection (closing)."""
        mock_resolved_config.covers_max_closure = 0

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=50)
        assert position == 0  # Fully closed
        assert reason == CoverMovementReason.CLOSING_HEAT_PROTECTION
        assert lockout_active is False

    def test_calculate_desired_position_let_light_in(self, cover_automation, mock_resolved_config):
        """Test desired position for letting light in (opening)."""
        mock_resolved_config.covers_min_closure = 100

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)
        assert position == 100  # Fully open
        assert reason == CoverMovementReason.OPENING_LET_LIGHT_IN

    def test_calculate_desired_position_passive_reopens_after_automation_closure(
        self, cover_automation, mock_resolved_config, mock_cover_pos_history_mgr
    ):
        """Passive mode reopens covers only when they were previously closed by automation."""

        mock_resolved_config.automatic_reopening_mode = ReopeningMode.PASSIVE
        mock_cover_pos_history_mgr.get_closed_by_automation_reason.return_value = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)
        assert position == 100
        assert reason == CoverMovementReason.OPENING_AFTER_HEAT_PROTECTION
        assert lockout_active is False

    def test_calculate_desired_position_passive_keeps_position_without_automation_closure(
        self, cover_automation, mock_resolved_config, mock_cover_pos_history_mgr
    ):
        """Passive mode should not reopen covers that were not closed by automation."""

        mock_resolved_config.automatic_reopening_mode = ReopeningMode.PASSIVE
        mock_cover_pos_history_mgr.get_closed_by_automation_reason.return_value = None

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)
        assert position == 50
        assert reason is None
        assert lockout_active is False

    def test_calculate_desired_position_off_never_reopens(self, cover_automation, mock_resolved_config, mock_cover_pos_history_mgr):
        """Off mode should suppress automatic reopening even after automation closures."""

        mock_resolved_config.automatic_reopening_mode = ReopeningMode.OFF
        mock_cover_pos_history_mgr.get_closed_by_automation_reason.return_value = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)
        assert position == 50
        assert reason is None
        assert lockout_active is False

    def test_calculate_desired_position_delays_auto_tilt_reopen_after_heat_protection(
        self, cover_automation, mock_resolved_config, mock_cover_pos_history_mgr
    ):
        """Auto-tilt heat-protection reopening should prepare tilt first when a delay is configured."""

        mock_resolved_config.automatic_reopening_mode = ReopeningMode.PASSIVE
        mock_resolved_config.tilt_mode_day = TiltMode.AUTO
        mock_resolved_config.tilt_open_to_cover_open_delay = 120
        mock_cover_pos_history_mgr.get_closed_by_automation_reason.return_value = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)

        assert position == 50
        assert reason == CoverMovementReason.PREPARING_REOPEN_AFTER_HEAT_PROTECTION
        assert lockout_active is False
        mock_cover_pos_history_mgr.set_delayed_reopen_action.assert_called_once()

    def test_calculate_desired_position_keeps_waiting_while_delayed_reopen_timer_active(
        self, cover_automation, mock_resolved_config, mock_cover_pos_history_mgr
    ):
        """Auto-tilt heat-protection reopening should wait until the delayed reopen timer expires."""

        mock_resolved_config.automatic_reopening_mode = ReopeningMode.PASSIVE
        mock_resolved_config.tilt_mode_day = TiltMode.AUTO
        mock_resolved_config.tilt_open_to_cover_open_delay = 120
        mock_cover_pos_history_mgr.get_closed_by_automation_reason.return_value = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION
        mock_cover_pos_history_mgr.get_delayed_reopen_action.return_value = MagicMock(
            reopen_at=datetime.now(timezone.utc) + timedelta(seconds=30)
        )

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)

        assert position == 50
        assert reason == CoverMovementReason.PREPARING_REOPEN_AFTER_HEAT_PROTECTION
        assert lockout_active is False
        mock_cover_pos_history_mgr.set_delayed_reopen_action.assert_not_called()

    def test_calculate_desired_position_reopens_after_delayed_auto_tilt_wait_elapsed(
        self, cover_automation, mock_resolved_config, mock_cover_pos_history_mgr
    ):
        """Auto-tilt heat-protection reopening should open the cover after the delay elapsed."""

        mock_resolved_config.automatic_reopening_mode = ReopeningMode.PASSIVE
        mock_resolved_config.tilt_mode_day = TiltMode.AUTO
        mock_resolved_config.tilt_open_to_cover_open_delay = 120
        mock_cover_pos_history_mgr.get_closed_by_automation_reason.return_value = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION
        mock_cover_pos_history_mgr.get_delayed_reopen_action.return_value = MagicMock(
            reopen_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)

        assert position == 100
        assert reason == CoverMovementReason.OPENING_AFTER_HEAT_PROTECTION
        assert lockout_active is False

    def test_calculate_desired_position_does_not_delay_when_day_tilt_mode_is_not_auto(
        self, cover_automation, mock_resolved_config, mock_cover_pos_history_mgr
    ):
        """Delayed reopening should be limited to effective day auto tilt mode."""

        mock_resolved_config.automatic_reopening_mode = ReopeningMode.PASSIVE
        mock_resolved_config.tilt_mode_day = TiltMode.MANUAL
        mock_resolved_config.tilt_open_to_cover_open_delay = 120
        mock_cover_pos_history_mgr.get_closed_by_automation_reason.return_value = const.TRANSL_LOGBOOK_REASON_HEAT_PROTECTION

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)

        assert position == 100
        assert reason == CoverMovementReason.OPENING_AFTER_HEAT_PROTECTION
        assert lockout_active is False
        mock_cover_pos_history_mgr.set_delayed_reopen_action.assert_not_called()

    def test_calculate_desired_position_after_manual_override_expired(self, cover_automation):
        """Active mode should use a dedicated reopening reason when manual override just expired."""

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(
            sensor_data,
            sun_hitting=False,
            current_pos=50,
            manual_override_just_expired=True,
        )
        assert position == 100
        assert reason == CoverMovementReason.OPENING_AFTER_MANUAL_OVERRIDE
        assert lockout_active is False

    def test_calculate_desired_position_reopens_after_evening_closure(self, cover_automation, mock_cover_pos_history_mgr):
        """Reopening after an evening-closure close should use the evening-closure reopening reason."""

        mock_cover_pos_history_mgr.get_closed_by_automation_reason.return_value = const.TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, _ = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)
        assert position == 100
        assert reason == CoverMovementReason.OPENING_AFTER_EVENING_CLOSURE

    def test_calculate_desired_position_with_max_closure_limit(self, cover_automation, mock_resolved_config, basic_config):
        """Test desired position with max closure limit."""
        mock_resolved_config.covers_max_closure = 30
        basic_config["cover.test_cover_max_closure"] = 20

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=50)
        assert position == 20  # Per-cover override
        assert reason == CoverMovementReason.CLOSING_HEAT_PROTECTION

    def test_calculate_desired_position_with_min_closure_limit(self, cover_automation, mock_resolved_config, basic_config):
        """Test desired position with min closure limit."""
        mock_resolved_config.covers_min_closure = 80
        basic_config["cover.test_cover_min_closure"] = 90

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)
        assert position == 90  # Per-cover override
        assert reason == CoverMovementReason.OPENING_LET_LIGHT_IN

    #
    # test_calculate_desired_position_sunset_closing_in_list
    #
    def test_calculate_desired_position_sunset_closing_in_list(self, cover_automation, mock_resolved_config):
        """Test evening closure takes priority when cover is in list and respects max closure limit."""

        mock_resolved_config.covers_max_closure = 0
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)

        # Sensor data with both sunset flag and heat protection conditions
        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=True,  # Sunset flag is set
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=50)
        assert position == 0  # Fully closed (max closure is 0, so no limit applied)
        assert reason == CoverMovementReason.CLOSING_AFTER_SUNSET  # Sunset takes priority

    #
    # test_calculate_desired_position_sunset_closing_not_in_list
    #
    def test_calculate_desired_position_sunset_closing_not_in_list(self, cover_automation, mock_resolved_config):
        """Test sunset flag ignored when cover not in list."""

        mock_resolved_config.covers_max_closure = 0
        mock_resolved_config.evening_closure_cover_list = ("cover.other",)

        # Sensor data with sunset flag but cover not in list
        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=True,  # Sunset flag is set
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=50)
        assert position == 0  # Still closed
        assert reason == CoverMovementReason.CLOSING_HEAT_PROTECTION  # Falls back to heat protection

    #
    # test_calculate_desired_position_sunset_closing_no_list_configured
    #
    def test_calculate_desired_position_sunset_closing_no_list_configured(self, cover_automation, mock_resolved_config):
        """Test sunset flag ignored when no cover list configured."""

        mock_resolved_config.covers_max_closure = 0
        mock_resolved_config.evening_closure_cover_list = ()  # Empty list

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=True,  # Sunset flag is set
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=50)
        assert position == 0  # Still closed
        assert reason == CoverMovementReason.CLOSING_HEAT_PROTECTION  # Falls back to heat protection

    #
    # test_calculate_desired_position_sunset_priority_over_opening
    #
    def test_calculate_desired_position_sunset_priority_over_opening(self, cover_automation, mock_resolved_config):
        """Test evening closure prevents opening for light and respects max closure limit."""

        mock_resolved_config.covers_max_closure = 15  # Set max closure limit
        mock_resolved_config.evening_closure_max_closure = 15
        mock_resolved_config.covers_min_closure = 100
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)

        # Conditions would normally open covers (not hot, not sunny)
        sensor_data = make_sensor_data(
            sun_azimuth=90.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=True,  # But sunset flag is set
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)
        assert position == 15  # Respects max closure limit
        assert reason == CoverMovementReason.CLOSING_AFTER_SUNSET  # Sunset takes priority

    #
    # test_calculate_desired_position_sunset_false_no_effect
    #
    def test_calculate_desired_position_sunset_false_no_effect(self, cover_automation, mock_resolved_config):
        """Test that sunset flag False doesn't affect normal operation."""

        mock_resolved_config.covers_min_closure = 100
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)

        # Conditions for opening
        sensor_data = make_sensor_data(
            sun_azimuth=90.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,  # Sunset flag is False
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)
        assert position == 100  # Open for light
        assert reason == CoverMovementReason.OPENING_LET_LIGHT_IN  # Normal behavior

    #
    # test_calculate_desired_position_sunset_closes_fully
    #
    def test_calculate_desired_position_sunset_closes_fully(self, cover_automation, mock_resolved_config):
        """Test evening closure respects max closure limit (global config)."""

        mock_resolved_config.covers_max_closure = 30
        mock_resolved_config.evening_closure_max_closure = 30
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=True,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=50)
        assert position == 30  # Respects max closure limit
        assert reason == CoverMovementReason.CLOSING_AFTER_SUNSET

    #
    # test_calculate_desired_position_sunset_with_per_cover_evening_closure_limit
    #
    def test_calculate_desired_position_sunset_with_per_cover_evening_closure_limit(
        self, cover_automation, mock_resolved_config, basic_config
    ):
        """Test evening closure respects per-cover max closure limit override."""

        mock_resolved_config.covers_max_closure = 30  # Global limit
        mock_resolved_config.evening_closure_max_closure = 30
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        basic_config[f"cover.test_{const.COVER_SFX_EVENING_CLOSURE_MAX_CLOSURE}"] = 20  # Per-cover override

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=25.0,
            temp_hot=False,
            weather_condition="clear",
            weather_sunny=False,
            evening_closure=True,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=50)
        assert position == 20  # Respects per-cover override
        assert reason == CoverMovementReason.CLOSING_AFTER_SUNSET


class TestCalculateDesiredPositionLockout:
    """Test lockout protection logic in _calculate_desired_position method."""

    def test_lockout_protection_heat_protection_active(self, cover_automation, mock_resolved_config, basic_config, mock_ha_interface):
        """Test lockout protection prevents closing for heat protection."""
        mock_resolved_config.covers_max_closure = 0
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON  # Window is open

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=50)

        # Lockout should prevent closing
        assert lockout_active is True
        assert position == 50  # Keeps current position
        assert reason is None  # No movement reason

    def test_lockout_protection_heat_protection_inactive(self, cover_automation, mock_resolved_config, basic_config, mock_ha_interface):
        """Test heat protection closes when lockout not active."""
        mock_resolved_config.covers_max_closure = 0
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = "off"  # Window is closed

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=50)

        # No lockout - should close
        assert lockout_active is False
        assert position == 0  # Closes
        assert reason == CoverMovementReason.CLOSING_HEAT_PROTECTION

    def test_lockout_protection_sunset_closing_active(self, cover_automation, mock_resolved_config, basic_config, mock_ha_interface):
        """Test lockout protection prevents closing after sunset."""
        mock_resolved_config.covers_max_closure = 0
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON  # Window is open

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="clear",
            weather_sunny=False,
            evening_closure=True,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=75)

        # Lockout should prevent evening closure
        assert lockout_active is True
        assert position == 75  # Keeps current position
        assert reason is None  # No movement reason

    def test_lockout_protection_sunset_closing_inactive(self, cover_automation, mock_resolved_config, basic_config, mock_ha_interface):
        """Test evening closure proceeds when lockout not active."""
        mock_resolved_config.covers_max_closure = 0
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = "off"  # Window is closed

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="clear",
            weather_sunny=False,
            evening_closure=True,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=75)

        # No lockout - should close for sunset
        assert lockout_active is False
        assert position == 0  # Closes
        assert reason == CoverMovementReason.CLOSING_AFTER_SUNSET

    def test_lockout_protection_not_checked_for_opening(self, cover_automation, mock_resolved_config, basic_config, mock_ha_interface):
        """Test lockout protection is not checked when opening (let light in)."""
        mock_resolved_config.covers_min_closure = 100
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON  # Window is open

        sensor_data = make_sensor_data(
            sun_azimuth=90.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=20)

        # Lockout doesn't apply to opening
        assert lockout_active is False
        assert position == 100  # Opens
        assert reason == CoverMovementReason.OPENING_LET_LIGHT_IN

    def test_lockout_protection_multiple_sensors_mixed_states(
        self, cover_automation, mock_resolved_config, basic_config, mock_ha_interface
    ):
        """Test lockout activates when any window sensor is open."""
        mock_resolved_config.covers_max_closure = 0
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1", "binary_sensor.window2", "binary_sensor.window3"]

        # Only one window is open
        def get_state(entity_id):
            return STATE_ON if entity_id == "binary_sensor.window2" else "off"

        mock_ha_interface.get_entity_state.side_effect = get_state

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=False,
            post_evening_closure=False,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=50)

        # Lockout should activate because one window is open
        assert lockout_active is True
        assert position == 50  # Keeps current position
        assert reason is None


class TestIsOpeningBlockAfterEveningClosureActive:
    """Test _is_opening_block_after_evening_closure_active method."""

    def test_block_tracks_post_evening_closure_true(self, cover_automation, mock_resolved_config):
        """Test block when post_evening_closure is True."""

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=True,
        )

        result = cover_automation._is_opening_block_after_evening_closure_active(sensor_data)
        assert result is True

    def test_block_tracks_post_evening_closure_false(self, cover_automation, mock_resolved_config):
        """Test block when post_evening_closure is False."""

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        result = cover_automation._is_opening_block_after_evening_closure_active(sensor_data)
        assert result is False

    def test_calculate_desired_position_block_prevents_opening(self, cover_automation, mock_resolved_config):
        """Test that opening block prevents opening but keeps current position."""

        mock_resolved_config.covers_min_closure = 100
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)

        # Conditions would normally open covers
        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=True,
        )

        # Test with current position at 30%
        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=30)
        assert position == 30  # Keeps current position
        assert reason is None  # No movement reason
        assert lockout_active is False

    def test_calculate_desired_position_block_does_not_apply_to_other_covers(self, cover_automation, mock_resolved_config):
        """Test that morning opening only affects covers in the evening closure list."""

        mock_resolved_config.covers_min_closure = 100
        mock_resolved_config.evening_closure_cover_list = ("cover.other",)

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=True,
        )

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False, current_pos=30)
        assert position == 100
        assert reason == CoverMovementReason.OPENING_LET_LIGHT_IN
        assert lockout_active is False

    def test_calculate_desired_position_block_allows_closing(self, cover_automation, mock_resolved_config):
        """Test that opening block does NOT prevent closing operations."""

        mock_resolved_config.covers_max_closure = 0

        # Conditions for heat protection closing
        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=False,
            post_evening_closure=True,
        )

        # Test that closing still happens despite opening block
        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=100)
        assert position == 0  # Closes fully
        assert reason == CoverMovementReason.CLOSING_HEAT_PROTECTION  # Closing still works
        assert lockout_active is False


class TestGetCoverClosureLimit:
    """Test _get_cover_closure_limit method."""

    def test_get_cover_closure_limit_max_global(self, cover_automation, mock_resolved_config):
        """Test getting max closure limit from global config."""
        mock_resolved_config.covers_max_closure = 25
        limit = cover_automation._get_cover_closure_limit(get_max=True)
        assert limit == 25

    def test_get_cover_closure_limit_min_global(self, cover_automation, mock_resolved_config):
        """Test getting min closure limit from global config."""
        mock_resolved_config.covers_min_closure = 75
        limit = cover_automation._get_cover_closure_limit(get_max=False)
        assert limit == 75

    def test_get_cover_closure_limit_max_per_cover(self, cover_automation, mock_resolved_config, basic_config):
        """Test getting max closure limit from per-cover override."""
        mock_resolved_config.covers_max_closure = 25
        basic_config["cover.test_cover_max_closure"] = 10
        limit = cover_automation._get_cover_closure_limit(get_max=True)
        assert limit == 10

    def test_get_cover_closure_limit_evening_max_global(self, cover_automation, mock_resolved_config):
        """Test getting the evening closure position from global config."""
        mock_resolved_config.evening_closure_max_closure = 15
        limit = cover_automation._get_cover_closure_limit(get_max=True, evening_closure=True)
        assert limit == 15

    def test_get_cover_closure_limit_evening_max_per_cover(self, cover_automation, mock_resolved_config, basic_config):
        """Test getting the evening closure position from a per-cover override."""
        mock_resolved_config.evening_closure_max_closure = 15
        basic_config[f"cover.test_{const.COVER_SFX_EVENING_CLOSURE_MAX_CLOSURE}"] = 5
        limit = cover_automation._get_cover_closure_limit(get_max=True, evening_closure=True)
        assert limit == 5

    def test_get_cover_closure_limit_evening_max_ignores_daytime_per_cover_max_without_override(
        self,
        cover_automation,
        mock_resolved_config,
        basic_config,
    ):
        """Test evening max uses the evening default when no dedicated evening override exists."""
        mock_resolved_config.evening_closure_max_closure = 15
        basic_config["cover.test_cover_max_closure"] = 10
        limit = cover_automation._get_cover_closure_limit(get_max=True, evening_closure=True)
        assert limit == 15

    def test_get_cover_closure_limit_min_per_cover(self, cover_automation, mock_resolved_config, basic_config):
        """Test getting min closure limit from per-cover override."""
        mock_resolved_config.covers_min_closure = 75
        basic_config["cover.test_cover_min_closure"] = 85
        limit = cover_automation._get_cover_closure_limit(get_max=False)
        assert limit == 85

    def test_get_cover_closure_limit_invalid_per_cover(self, cover_automation, mock_resolved_config, basic_config):
        """Test fallback to global when per-cover value is invalid."""
        mock_resolved_config.covers_max_closure = 25
        basic_config["cover.test_cover_max_closure"] = "invalid"
        limit = cover_automation._get_cover_closure_limit(get_max=True)
        assert limit == 25


class TestGetEffectiveTempHot:
    """Test _get_effective_temp_hot method."""

    def test_get_effective_temp_hot_uses_global_sensor_state(self, cover_automation, sensor_data, mock_logger):
        """Test that the global effective hot state is used when no per-cover override exists."""

        sensor_data.temp_hot = True

        result = cover_automation._get_effective_temp_hot(sensor_data)

        assert result is True
        mock_logger.debug.assert_not_called()

    def test_get_effective_temp_hot_per_cover_true_overrides_global_false(self, cover_automation, basic_config, sensor_data, mock_logger):
        """Test that per-cover True overrides a global False hot state."""

        basic_config[f"cover.test_{const.COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"] = True
        sensor_data.temp_hot = False

        result = cover_automation._get_effective_temp_hot(sensor_data)

        assert result is True
        mock_logger.debug.assert_called_once_with("[cover.test] Per-cover weather hot external control active: hot")

    def test_get_effective_temp_hot_per_cover_false_overrides_global_true(self, cover_automation, basic_config, sensor_data, mock_logger):
        """Test that per-cover False overrides a global True hot state."""

        basic_config[f"cover.test_{const.COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"] = False
        sensor_data.temp_hot = True

        result = cover_automation._get_effective_temp_hot(sensor_data)

        assert result is False
        mock_logger.debug.assert_called_once_with("[cover.test] Per-cover weather hot external control active: not hot")

    def test_calculate_desired_position_uses_per_cover_hot_override(self, cover_automation, basic_config, sensor_data):
        """Test that a per-cover hot override changes the heat-protection branch outcome."""

        basic_config[f"cover.test_{const.COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}"] = True
        sensor_data.temp_hot = False
        sensor_data.weather_sunny = True

        position, reason, lockout_active = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True, current_pos=100)

        assert position == 0
        assert reason == CoverMovementReason.CLOSING_HEAT_PROTECTION
        assert lockout_active is False


class TestIsLockoutActive:
    """Test _is_lockout_protection_active method."""

    def test_is_lockout_active_no_sensors_configured(self, cover_automation):
        """Test when no window sensors are configured."""
        result = cover_automation._is_lockout_protection_active(CoverMovementReason.CLOSING_HEAT_PROTECTION)
        assert result is False

    def test_is_lockout_active_all_windows_closed(self, cover_automation, basic_config, mock_ha_interface):
        """Test when all windows are closed."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1", "binary_sensor.window2"]
        mock_ha_interface.get_entity_state.return_value = "off"

        result = cover_automation._is_lockout_protection_active(CoverMovementReason.CLOSING_HEAT_PROTECTION)
        assert result is False

    def test_is_lockout_active_window_open_closing(self, cover_automation, basic_config, mock_ha_interface):
        """Test lockout when window is open and cover wants to close."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON

        result = cover_automation._is_lockout_protection_active(CoverMovementReason.CLOSING_HEAT_PROTECTION)
        assert result is True

    def test_is_lockout_active_window_open_opening(self, cover_automation, basic_config, mock_ha_interface):
        """Test no lockout when window is open but cover wants to open."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON

        result = cover_automation._is_lockout_protection_active(CoverMovementReason.OPENING_LET_LIGHT_IN)
        assert result is False

    def test_is_lockout_active_multiple_sensors_one_open(self, cover_automation, basic_config, mock_ha_interface):
        """Test lockout when one of multiple windows is open."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1", "binary_sensor.window2"]

        def get_state(entity_id):
            return STATE_ON if entity_id == "binary_sensor.window2" else "off"

        mock_ha_interface.get_entity_state.side_effect = get_state

        result = cover_automation._is_lockout_protection_active(CoverMovementReason.CLOSING_HEAT_PROTECTION)
        assert result is True

    def test_is_lockout_active_sunset_closing(self, cover_automation, basic_config, mock_ha_interface):
        """Test lockout applies to evening closure as well."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON

        result = cover_automation._is_lockout_protection_active(CoverMovementReason.CLOSING_AFTER_SUNSET)
        assert result is True


class TestMaoveCoverIfNeeded:
    """Test _move_cover_if_needed method."""

    async def test_move_cover_if_needed_no_change(self, cover_automation):
        """Test when no movement is needed (same position)."""
        movement_needed, actual_pos, message = await cover_automation._move_cover_if_needed(
            current_pos=50,
            desired_pos=50,
            features=CoverEntityFeature.SET_POSITION,
            movement_reason=CoverMovementReason.CLOSING_HEAT_PROTECTION,
        )
        assert movement_needed is False
        assert actual_pos is None
        assert message == "No movement needed"

    async def test_move_cover_if_needed_minor_adjustment(self, cover_automation, mock_resolved_config):
        """Test when movement is below minimum delta."""
        mock_resolved_config.covers_min_position_delta = 5
        movement_needed, actual_pos, message = await cover_automation._move_cover_if_needed(
            current_pos=50,
            desired_pos=52,
            features=CoverEntityFeature.SET_POSITION,
            movement_reason=CoverMovementReason.CLOSING_HEAT_PROTECTION,
        )
        assert movement_needed is False
        assert actual_pos is None
        assert message == "Skipped minor adjustment"

    async def test_move_cover_if_needed_closing_heat_protection(self, cover_automation, mock_ha_interface, mock_cover_pos_history_mgr):
        """Test moving cover for heat protection."""
        mock_ha_interface.set_cover_position.return_value = 20

        movement_needed, actual_pos, message = await cover_automation._move_cover_if_needed(
            current_pos=100,
            desired_pos=20,
            features=CoverEntityFeature.SET_POSITION,
            movement_reason=CoverMovementReason.CLOSING_HEAT_PROTECTION,
        )

        assert movement_needed is True
        assert actual_pos == 20
        assert message == "Moved cover"
        mock_ha_interface.set_cover_position.assert_called_once_with("cover.test", 20, CoverEntityFeature.SET_POSITION)
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", 20, cover_moved=True)
        mock_ha_interface.add_logbook_entry.assert_called_once()

    async def test_move_cover_if_needed_opening_let_light_in(self, cover_automation, mock_ha_interface, mock_cover_pos_history_mgr):
        """Test moving cover to let light in."""
        mock_ha_interface.set_cover_position.return_value = 80

        movement_needed, actual_pos, message = await cover_automation._move_cover_if_needed(
            current_pos=20,
            desired_pos=80,
            features=CoverEntityFeature.SET_POSITION,
            movement_reason=CoverMovementReason.OPENING_LET_LIGHT_IN,
        )

        assert movement_needed is True
        assert actual_pos == 80
        assert message == "Moved cover"
        mock_ha_interface.add_logbook_entry.assert_called_once()

    async def test_move_cover_if_needed_opening_after_heat_protection(
        self, cover_automation, mock_ha_interface, mock_cover_pos_history_mgr
    ):
        """Test moving cover when reopening after heat protection ends."""

        mock_ha_interface.set_cover_position.return_value = 80

        movement_needed, actual_pos, message = await cover_automation._move_cover_if_needed(
            current_pos=20,
            desired_pos=80,
            features=CoverEntityFeature.SET_POSITION,
            movement_reason=CoverMovementReason.OPENING_AFTER_HEAT_PROTECTION,
        )

        assert movement_needed is True
        assert actual_pos == 80
        assert message == "Moved cover"
        call_kwargs = mock_ha_interface.add_logbook_entry.call_args[1]
        assert call_kwargs["reason_key"] == const.TRANSL_LOGBOOK_REASON_END_HEAT_PROTECTION

    async def test_move_cover_if_needed_opening_after_evening_closure(
        self, cover_automation, mock_ha_interface, mock_cover_pos_history_mgr
    ):
        """Test moving cover when reopening after evening closure ends."""

        mock_ha_interface.set_cover_position.return_value = 80

        movement_needed, actual_pos, message = await cover_automation._move_cover_if_needed(
            current_pos=20,
            desired_pos=80,
            features=CoverEntityFeature.SET_POSITION,
            movement_reason=CoverMovementReason.OPENING_AFTER_EVENING_CLOSURE,
        )

        assert movement_needed is True
        assert actual_pos == 80
        assert message == "Moved cover"
        call_kwargs = mock_ha_interface.add_logbook_entry.call_args[1]
        assert call_kwargs["reason_key"] == const.TRANSL_LOGBOOK_REASON_END_EVENING_CLOSURE

    async def test_move_cover_if_needed_opening_after_manual_override(
        self, cover_automation, mock_ha_interface, mock_cover_pos_history_mgr
    ):
        """Test moving cover when reopening after manual override expires."""

        mock_ha_interface.set_cover_position.return_value = 80

        movement_needed, actual_pos, message = await cover_automation._move_cover_if_needed(
            current_pos=20,
            desired_pos=80,
            features=CoverEntityFeature.SET_POSITION,
            movement_reason=CoverMovementReason.OPENING_AFTER_MANUAL_OVERRIDE,
        )

        assert movement_needed is True
        assert actual_pos == 80
        assert message == "Moved cover"
        call_kwargs = mock_ha_interface.add_logbook_entry.call_args[1]
        assert call_kwargs["reason_key"] == const.TRANSL_LOGBOOK_REASON_END_MANUAL_OVERRIDE

    async def test_process_marks_manual_override_blocked_when_skipping(
        self, cover_automation, mock_cover_pos_history_mgr, mock_state, sensor_data
    ):
        """Manual override skips should mark the cover as blocked by manual override."""

        entry = PositionEntry(position=0, timestamp=datetime.now(timezone.utc) - timedelta(seconds=30), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry
        mock_state.attributes[ATTR_CURRENT_POSITION] = 50

        await cover_automation.process(mock_state, sensor_data)

        mock_cover_pos_history_mgr.mark_manual_override_blocked.assert_called_once_with("cover.test")

    async def test_process_clears_manual_override_block_and_reopens_with_reason(
        self, cover_automation, mock_cover_pos_history_mgr, mock_state, sensor_data, mock_ha_interface
    ):
        """The first cycle after manual override expiry should use the dedicated reopening reason."""

        entry = PositionEntry(position=0, timestamp=datetime.now(timezone.utc) - timedelta(seconds=3700), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry
        mock_cover_pos_history_mgr.was_manual_override_blocking.return_value = True
        mock_state.attributes[ATTR_CURRENT_POSITION] = 0
        mock_ha_interface.set_cover_position.return_value = 100

        sensor_data = make_sensor_data(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=False,
            post_evening_closure=False,
        )

        await cover_automation.process(mock_state, sensor_data)

        mock_cover_pos_history_mgr.clear_manual_override_blocked.assert_called_once_with("cover.test")
        call_kwargs = mock_ha_interface.add_logbook_entry.call_args[1]
        assert call_kwargs["reason_key"] == const.TRANSL_LOGBOOK_REASON_END_MANUAL_OVERRIDE

    async def test_move_cover_if_needed_closing_after_sunset(self, cover_automation, mock_ha_interface, mock_cover_pos_history_mgr):
        """Test moving cover after sunset."""
        mock_ha_interface.set_cover_position.return_value = 0

        movement_needed, actual_pos, message = await cover_automation._move_cover_if_needed(
            current_pos=100,
            desired_pos=0,
            features=CoverEntityFeature.SET_POSITION,
            movement_reason=CoverMovementReason.CLOSING_AFTER_SUNSET,
        )

        assert movement_needed is True
        assert actual_pos == 0
        assert message == "Moved cover"
        mock_ha_interface.set_cover_position.assert_called_once_with("cover.test", 0, CoverEntityFeature.SET_POSITION)
        mock_cover_pos_history_mgr.add.assert_called_once_with("cover.test", 0, cover_moved=True)
        # Verify logbook entry was called with correct parameters
        mock_ha_interface.add_logbook_entry.assert_called_once()
        call_kwargs = mock_ha_interface.add_logbook_entry.call_args[1]
        assert call_kwargs["verb_key"] == const.TRANSL_LOGBOOK_VERB_CLOSING
        assert call_kwargs["reason_key"] == const.TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET
        assert call_kwargs["entity_id"] == "cover.test"
        assert call_kwargs["target_pos"] == 0

    async def test_move_cover_if_needed_error_handling(self, cover_automation, mock_ha_interface):
        """Test error handling during cover movement."""
        mock_ha_interface.set_cover_position.side_effect = Exception("Service call failed")

        movement_needed, actual_pos, message = await cover_automation._move_cover_if_needed(
            current_pos=100,
            desired_pos=20,
            features=CoverEntityFeature.SET_POSITION,
            movement_reason=CoverMovementReason.CLOSING_HEAT_PROTECTION,
        )

        assert movement_needed is False
        assert actual_pos is None
        assert "Error" in message


class TestProcessMethod:
    """Test the main process method."""

    async def test_process_missing_azimuth(self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr):
        """Test process when cover azimuth is missing."""
        cover_automation.config = {}  # No azimuth configured
        result = await cover_automation.process(mock_state, sensor_data)
        # Result should be CoverState with no fields set when azimuth is missing
        assert result.cover_azimuth is None

    async def test_process_invalid_state(self, cover_automation, sensor_data, mock_cover_pos_history_mgr):
        """Test process when cover state is invalid."""
        result = await cover_automation.process(None, sensor_data)
        assert result.cover_azimuth is not None
        assert result.state is None  # State validation failed

    async def test_process_cover_moving(self, cover_automation, sensor_data, mock_cover_pos_history_mgr):
        """Test process when cover is moving."""
        state = MagicMock()
        state.state = STATE_OPENING
        result = await cover_automation.process(state, sensor_data)
        assert result.state == STATE_OPENING

    async def test_process_manual_override_active(
        self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr, mock_resolved_config
    ):
        """Test process when manual override is active."""
        mock_resolved_config.manual_override_duration = 3600
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) - timedelta(seconds=100), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry

        result = await cover_automation.process(mock_state, sensor_data)
        assert result.pos_current is not None
        # Should not have POS_TARGET_FINAL since manual override prevents movement
        assert result.pos_target_final is None

    async def test_process_manual_override_ignored_for_evening_closure(
        self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr, mock_resolved_config, mock_ha_interface
    ):
        """Test evening closure can bypass manual override when configured."""
        mock_resolved_config.manual_override_duration = 3600
        mock_resolved_config.evening_closure_ignore_manual_override_duration = True
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        sensor_data.evening_closure = True
        mock_ha_interface.set_cover_position.return_value = 0
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) - timedelta(seconds=100), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry

        result = await cover_automation.process(mock_state, sensor_data)

        assert result.pos_target_desired == 0

    async def test_process_manual_override_not_ignored_for_non_evening_cover(
        self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr, mock_resolved_config
    ):
        """Test evening-closure bypass does not apply outside the configured list."""
        mock_resolved_config.manual_override_duration = 3600
        mock_resolved_config.evening_closure_ignore_manual_override_duration = True
        mock_resolved_config.evening_closure_cover_list = ("cover.other",)
        sensor_data.evening_closure = True
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) - timedelta(seconds=100), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry

        result = await cover_automation.process(mock_state, sensor_data)

        assert result.pos_current is not None
        assert result.pos_target_final is None

    async def test_process_recloses_cover_during_post_evening_closure_when_enabled(
        self, cover_automation, mock_state, sensor_data, mock_resolved_config, mock_ha_interface
    ):
        """Test keep-closed re-closes an evening cover during the overnight block."""
        mock_resolved_config.evening_closure_keep_closed = True
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        sensor_data.post_evening_closure = True
        sensor_data.evening_closure = False
        sensor_data.temp_hot = False
        sensor_data.weather_sunny = False
        mock_ha_interface.set_cover_position.return_value = 0
        mock_state.attributes[ATTR_CURRENT_POSITION] = 100

        result = await cover_automation.process(mock_state, sensor_data)

        assert result.pos_target_desired == 0
        assert result.pos_target_final == 0

    async def test_process_respects_manual_override_during_post_evening_closure_keep_closed(
        self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr, mock_resolved_config
    ):
        """Test keep-closed waits for manual override expiry before re-closing."""
        mock_resolved_config.manual_override_duration = 3600
        mock_resolved_config.evening_closure_keep_closed = True
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        sensor_data.post_evening_closure = True
        sensor_data.evening_closure = False
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) - timedelta(seconds=100), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry

        result = await cover_automation.process(mock_state, sensor_data)

        assert result.pos_current is not None
        assert result.pos_target_final is None

    async def test_process_successful_automation(
        self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr, mock_ha_interface
    ):
        """Test successful automation process."""
        mock_ha_interface.set_cover_position.return_value = 0
        mock_state.attributes[ATTR_CURRENT_POSITION] = 100

        result = await cover_automation.process(mock_state, sensor_data)

        assert result.cover_azimuth is not None
        assert result.state is not None
        assert result.supported_features is not None
        assert result.pos_current is not None
        assert result.sun_hitting is not None
        assert result.sun_azimuth_diff is not None
        assert result.pos_target_desired is not None
        assert result.lockout_protection is not None

    async def test_process_lockout_protection_active(
        self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr, mock_ha_interface, basic_config
    ):
        """Test process when lockout protection is active."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON
        mock_state.attributes[ATTR_CURRENT_POSITION] = 100

        result = await cover_automation.process(mock_state, sensor_data)

        assert result.lockout_protection is True
        # Should not have POS_TARGET_FINAL since lockout prevents movement
        assert result.pos_target_final is None


class TestLogCoverMsg:
    """Test _log_cover_msg method."""

    def test_log_cover_msg_debug(self, cover_automation, mock_logger):
        """Test logging debug message."""

        cover_automation._log_cover_msg("Test message", const.LogSeverity.DEBUG)
        mock_logger.debug.assert_called_once()
        assert "cover.test" in mock_logger.debug.call_args[0][0]
        assert "Test message" in mock_logger.debug.call_args[0][0]

    def test_log_cover_msg_info(self, cover_automation, mock_logger):
        """Test logging info message."""

        cover_automation._log_cover_msg("Test message", const.LogSeverity.INFO)
        mock_logger.info.assert_called_once()

    def test_log_cover_msg_warning(self, cover_automation, mock_logger):
        """Test logging warning message."""

        cover_automation._log_cover_msg("Test message", const.LogSeverity.WARNING)
        mock_logger.warning.assert_called_once()

    def test_log_cover_msg_error(self, cover_automation, mock_logger):
        """Test logging error message."""

        cover_automation._log_cover_msg("Test message", const.LogSeverity.ERROR)
        mock_logger.error.assert_called_once()
