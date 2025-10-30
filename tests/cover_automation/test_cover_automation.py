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
from unittest.mock import AsyncMock, MagicMock, patch

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
from custom_components.smart_cover_automation.cover_automation import (
    CoverAutomation,
    CoverMovementReason,
    SensorData,
)
from custom_components.smart_cover_automation.cover_position_history import PositionEntry


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
    ha_interface.get_entity_state = MagicMock(return_value=None)
    ha_interface.set_cover_position = AsyncMock(return_value=50)
    ha_interface.add_logbook_entry = AsyncMock()
    return ha_interface


@pytest.fixture
def mock_cover_pos_history_mgr():
    """Create a mock cover position history manager."""
    mgr = MagicMock()
    mgr.get_latest_entry = MagicMock(return_value=None)
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
def cover_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface):
    """Create a CoverAutomation instance for testing."""
    return CoverAutomation(
        entity_id="cover.test",
        resolved=mock_resolved_config,
        config=basic_config,
        cover_pos_history_mgr=mock_cover_pos_history_mgr,
        ha_interface=mock_ha_interface,
    )


@pytest.fixture
def sensor_data():
    """Create sample sensor data."""
    return SensorData(
        sun_azimuth=180.0,
        sun_elevation=45.0,
        temp_max=30.0,
        temp_hot=True,
        weather_condition="sunny",
        weather_sunny=True,
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
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface
    ):
        """Test that all dependencies are stored correctly."""
        cover_auto = CoverAutomation(
            entity_id="cover.living_room",
            resolved=mock_resolved_config,
            config=basic_config,
            cover_pos_history_mgr=mock_cover_pos_history_mgr,
            ha_interface=mock_ha_interface,
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

    def test_get_cover_azimuth_missing(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test handling missing cover azimuth."""
        config = {}  # No azimuth configured
        cover_auto = CoverAutomation(
            entity_id="cover.test",
            resolved=mock_resolved_config,
            config=config,
            cover_pos_history_mgr=mock_cover_pos_history_mgr,
            ha_interface=mock_ha_interface,
        )
        azimuth = cover_auto._get_cover_azimuth()
        assert azimuth is None

    def test_get_cover_azimuth_invalid_type(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test handling invalid cover azimuth type."""
        config = {"cover.test_cover_azimuth": "invalid"}
        cover_auto = CoverAutomation(
            entity_id="cover.test",
            resolved=mock_resolved_config,
            config=config,
            cover_pos_history_mgr=mock_cover_pos_history_mgr,
            ha_interface=mock_ha_interface,
        )
        azimuth = cover_auto._get_cover_azimuth()
        assert azimuth is None

    def test_get_cover_azimuth_zero(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface):
        """Test cover azimuth of zero (North)."""
        config = {"cover.test_cover_azimuth": 0.0}
        cover_auto = CoverAutomation(
            entity_id="cover.test",
            resolved=mock_resolved_config,
            config=config,
            cover_pos_history_mgr=mock_cover_pos_history_mgr,
            ha_interface=mock_ha_interface,
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

        sensor_data = SensorData(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
        )

        position, reason = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True)
        assert position == 0  # Fully closed
        assert reason == CoverMovementReason.CLOSING_HEAT_PROTECTION

    def test_calculate_desired_position_let_light_in(self, cover_automation, mock_resolved_config):
        """Test desired position for letting light in (opening)."""
        mock_resolved_config.covers_min_closure = 100

        sensor_data = SensorData(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
        )

        position, reason = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False)
        assert position == 100  # Fully open
        assert reason == CoverMovementReason.OPENING_LET_LIGHT_IN

    def test_calculate_desired_position_with_max_closure_limit(self, cover_automation, mock_resolved_config, basic_config):
        """Test desired position with max closure limit."""
        mock_resolved_config.covers_max_closure = 30
        basic_config["cover.test_cover_max_closure"] = 20

        sensor_data = SensorData(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
        )

        position, reason = cover_automation._calculate_desired_position(sensor_data, sun_hitting=True)
        assert position == 20  # Per-cover override
        assert reason == CoverMovementReason.CLOSING_HEAT_PROTECTION

    def test_calculate_desired_position_with_min_closure_limit(self, cover_automation, mock_resolved_config, basic_config):
        """Test desired position with min closure limit."""
        mock_resolved_config.covers_min_closure = 80
        basic_config["cover.test_cover_min_closure"] = 90

        sensor_data = SensorData(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
        )

        position, reason = cover_automation._calculate_desired_position(sensor_data, sun_hitting=False)
        assert position == 90  # Per-cover override
        assert reason == CoverMovementReason.OPENING_LET_LIGHT_IN


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


class TestCheckLockoutProtection:
    """Test _check_lockout_protection method."""

    def test_check_lockout_protection_no_sensors_configured(self, cover_automation):
        """Test when no window sensors are configured."""
        result = cover_automation._check_lockout_protection(CoverMovementReason.CLOSING_HEAT_PROTECTION)
        assert result is False

    def test_check_lockout_protection_all_windows_closed(self, cover_automation, basic_config, mock_ha_interface):
        """Test when all windows are closed."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1", "binary_sensor.window2"]
        mock_ha_interface.get_entity_state.return_value = "off"

        result = cover_automation._check_lockout_protection(CoverMovementReason.CLOSING_HEAT_PROTECTION)
        assert result is False

    def test_check_lockout_protection_window_open_closing(self, cover_automation, basic_config, mock_ha_interface):
        """Test lockout when window is open and cover wants to close."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON

        result = cover_automation._check_lockout_protection(CoverMovementReason.CLOSING_HEAT_PROTECTION)
        assert result is True

    def test_check_lockout_protection_window_open_opening(self, cover_automation, basic_config, mock_ha_interface):
        """Test no lockout when window is open but cover wants to open."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON

        result = cover_automation._check_lockout_protection(CoverMovementReason.OPENING_LET_LIGHT_IN)
        assert result is False

    def test_check_lockout_protection_multiple_sensors_one_open(self, cover_automation, basic_config, mock_ha_interface):
        """Test lockout when one of multiple windows is open."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1", "binary_sensor.window2"]

        def get_state(entity_id):
            return STATE_ON if entity_id == "binary_sensor.window2" else "off"

        mock_ha_interface.get_entity_state.side_effect = get_state

        result = cover_automation._check_lockout_protection(CoverMovementReason.CLOSING_HEAT_PROTECTION)
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
        assert result == {}

    async def test_process_invalid_state(self, cover_automation, sensor_data, mock_cover_pos_history_mgr):
        """Test process when cover state is invalid."""
        result = await cover_automation.process(None, sensor_data)
        assert const.COVER_ATTR_COVER_AZIMUTH in result
        assert len(result) == 1  # Only azimuth added

    async def test_process_cover_moving(self, cover_automation, sensor_data, mock_cover_pos_history_mgr):
        """Test process when cover is moving."""
        state = MagicMock()
        state.state = STATE_OPENING
        result = await cover_automation.process(state, sensor_data)
        assert const.COVER_ATTR_STATE in result
        assert result[const.COVER_ATTR_STATE] == STATE_OPENING

    async def test_process_manual_override_active(
        self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr, mock_resolved_config
    ):
        """Test process when manual override is active."""
        mock_resolved_config.manual_override_duration = 3600
        entry = PositionEntry(position=50, timestamp=datetime.now(timezone.utc) - timedelta(seconds=100), cover_moved=True)
        mock_cover_pos_history_mgr.get_latest_entry.return_value = entry

        result = await cover_automation.process(mock_state, sensor_data)
        assert const.COVER_ATTR_POS_CURRENT in result
        # Should not have POS_TARGET_FINAL since manual override prevents movement

    async def test_process_successful_automation(
        self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr, mock_ha_interface
    ):
        """Test successful automation process."""
        mock_ha_interface.set_cover_position.return_value = 0
        mock_state.attributes[ATTR_CURRENT_POSITION] = 100

        result = await cover_automation.process(mock_state, sensor_data)

        assert const.COVER_ATTR_COVER_AZIMUTH in result
        assert const.COVER_ATTR_STATE in result
        assert const.COVER_ATTR_SUPPORTED_FEATURES in result
        assert const.COVER_ATTR_POS_CURRENT in result
        assert const.COVER_ATTR_SUN_HITTING in result
        assert const.COVER_ATTR_SUN_AZIMUTH_DIFF in result
        assert const.COVER_ATTR_POS_TARGET_DESIRED in result
        assert const.COVER_ATTR_LOCKOUT_PROTECTION in result
        assert const.COVER_ATTR_POS_HISTORY in result

    async def test_process_lockout_protection_active(
        self, cover_automation, mock_state, sensor_data, mock_cover_pos_history_mgr, mock_ha_interface, basic_config
    ):
        """Test process when lockout protection is active."""
        basic_config["cover.test_cover_window_sensors"] = ["binary_sensor.window1"]
        mock_ha_interface.get_entity_state.return_value = STATE_ON
        mock_state.attributes[ATTR_CURRENT_POSITION] = 100

        result = await cover_automation.process(mock_state, sensor_data)

        assert const.COVER_ATTR_LOCKOUT_PROTECTION in result
        assert result[const.COVER_ATTR_LOCKOUT_PROTECTION] is True
        # Should not have POS_TARGET_FINAL since lockout prevents movement
        assert const.COVER_ATTR_POS_TARGET_FINAL not in result


class TestLogCoverMsg:
    """Test _log_cover_msg method."""

    def test_log_cover_msg_debug(self, cover_automation):
        """Test logging debug message."""
        with patch.object(const.LOGGER, "debug") as mock_debug:
            cover_automation._log_cover_msg("Test message", const.LogSeverity.DEBUG)
            mock_debug.assert_called_once()
            assert "cover.test" in mock_debug.call_args[0][0]
            assert "Test message" in mock_debug.call_args[0][0]

    def test_log_cover_msg_info(self, cover_automation):
        """Test logging info message."""
        with patch.object(const.LOGGER, "info") as mock_info:
            cover_automation._log_cover_msg("Test message", const.LogSeverity.INFO)
            mock_info.assert_called_once()

    def test_log_cover_msg_warning(self, cover_automation):
        """Test logging warning message."""
        with patch.object(const.LOGGER, "warning") as mock_warning:
            cover_automation._log_cover_msg("Test message", const.LogSeverity.WARNING)
            mock_warning.assert_called_once()

    def test_log_cover_msg_error(self, cover_automation):
        """Test logging error message."""
        with patch.object(const.LOGGER, "error") as mock_error:
            cover_automation._log_cover_msg("Test message", const.LogSeverity.ERROR)
            mock_error.assert_called_once()
