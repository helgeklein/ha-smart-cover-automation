"""Unit tests for tilt angle control in CoverAutomation.

Tests cover:
- Auto tilt formula calculations
- Tilt mode resolution (per-cover vs global)
- Tilt application for all modes (open, closed, manual, auto, set_value)
- Tilt delta threshold
- Tilt during lock modes
- Tilt in process() flow
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, ATTR_CURRENT_TILT_POSITION, CoverEntityFeature
from homeassistant.const import STATE_OPEN

from custom_components.smart_cover_automation.const import LockMode, TiltMode
from custom_components.smart_cover_automation.cover_automation import (
    CoverAutomation,
    CoverMovementReason,
    CoverState,
    SensorData,
)

# ───────────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_resolved_config():
    """Create a mock resolved configuration with tilt defaults."""

    resolved = MagicMock()
    resolved.covers_max_closure = 0
    resolved.covers_min_closure = 100
    resolved.sun_elevation_threshold = 10.0
    resolved.sun_azimuth_tolerance = 90.0
    resolved.manual_override_duration = 3600
    resolved.covers_min_position_delta = 5
    resolved.lock_mode = LockMode.UNLOCKED
    resolved.block_opening_after_evening_closure = False
    resolved.evening_closure_enabled = False
    resolved.evening_closure_cover_list = ()
    resolved.tilt_mode_day = TiltMode.OPEN
    resolved.tilt_mode_night = TiltMode.CLOSED
    resolved.tilt_set_value_day = 50
    resolved.tilt_set_value_night = 0
    resolved.tilt_min_change_delta = 5
    resolved.tilt_slat_overlap_ratio = 0.9
    return resolved


@pytest.fixture
def mock_ha_interface():
    """Create a mock Home Assistant interface."""

    ha_interface = MagicMock()
    ha_interface.get_entity_state = MagicMock(return_value=None)
    ha_interface.get_sun_state = MagicMock(return_value="above_horizon")
    ha_interface.set_cover_position = AsyncMock(return_value=50)
    ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)
    ha_interface.add_logbook_entry = AsyncMock()
    return ha_interface


@pytest.fixture
def mock_cover_pos_history_mgr():
    """Create a mock cover position history manager."""

    mgr = MagicMock()
    mgr.get_latest_entry = MagicMock(return_value=None)
    mgr.get_recent_tilt_action = MagicMock(return_value=None)
    mgr.set_recent_tilt_action = MagicMock()
    mgr.clear_recent_tilt_action = MagicMock()
    mgr.add = MagicMock()
    mgr.get_entries = MagicMock(return_value=[])
    return mgr


@pytest.fixture
def mock_logger():
    """Create a mock logger."""

    logger = MagicMock()
    return logger


@pytest.fixture
def basic_config():
    """Create a basic test configuration with cover azimuth."""

    return {
        "cover.test_cover_azimuth": 180.0,
    }


@pytest.fixture
def tilt_features():
    """Return features bitmask for a cover that supports position and tilt."""

    return CoverEntityFeature.SET_POSITION | CoverEntityFeature.SET_TILT_POSITION


@pytest.fixture
def sensor_data():
    """Create sample sensor data for a sunny day with sun hitting south."""

    return SensorData(
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
def mock_state(tilt_features):
    """Create a mock cover state with tilt support."""

    state = MagicMock()
    state.state = STATE_OPEN
    state.attributes = {
        ATTR_CURRENT_POSITION: 100,
        ATTR_CURRENT_TILT_POSITION: 50,
        "supported_features": tilt_features,
    }
    return state


#
# _make_automation
#
def _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger):
    """Helper to create a CoverAutomation instance."""

    return CoverAutomation(
        entity_id="cover.test",
        resolved=mock_resolved_config,
        config=basic_config,
        cover_pos_history_mgr=mock_cover_pos_history_mgr,
        ha_interface=mock_ha_interface,
        logger=mock_logger,
    )


# ───────────────────────────────────────────────────────────────────────
# Auto tilt formula tests
# ───────────────────────────────────────────────────────────────────────


class TestCalculateAutoTilt:
    """Tests for _calculate_auto_tilt static method."""

    #
    # test_sun_at_horizon_returns_zero
    #
    def test_sun_at_horizon_returns_zero(self) -> None:
        """Sun at or below horizon should return fully closed tilt (0)."""

        assert CoverAutomation._calculate_auto_tilt(0, 0, 0.9) == 0
        assert CoverAutomation._calculate_auto_tilt(-5, 0, 0.9) == 0

    #
    # test_typical_20deg_elevation_0_hsa
    #
    def test_typical_20deg_elevation_0_hsa(self) -> None:
        """At 20° elevation, 0° HSA, d/L=0.9: tilt should be ~58%."""

        result = CoverAutomation._calculate_auto_tilt(20, 0, 0.9)
        # The physics formula gives ~58% for these inputs
        assert 55 <= result <= 62

    #
    # test_high_elevation_gives_more_open
    #
    def test_high_elevation_gives_more_open(self) -> None:
        """Higher sun elevation should give a more open tilt (higher %)."""

        low = CoverAutomation._calculate_auto_tilt(15, 0, 0.9)
        high = CoverAutomation._calculate_auto_tilt(60, 0, 0.9)
        assert high > low

    #
    # test_large_azimuth_diff_gives_more_open
    #
    def test_large_azimuth_diff_gives_more_open(self) -> None:
        """When sun is more to the side (large azimuth diff), tilt can be more open."""

        direct = CoverAutomation._calculate_auto_tilt(30, 10, 0.9)
        oblique = CoverAutomation._calculate_auto_tilt(30, 60, 0.9)
        assert oblique >= direct

    #
    # test_result_clamped_0_100
    #
    def test_result_clamped_0_100(self) -> None:
        """Result should always be in 0-100 range."""

        for elev in [1, 10, 30, 45, 60, 80, 89]:
            for hsa in [0, 30, 60, 85]:
                for ratio in [0.5, 0.7, 0.9, 1.0]:
                    result = CoverAutomation._calculate_auto_tilt(elev, hsa, ratio)
                    assert 0 <= result <= 100, f"Out of range: elev={elev}, hsa={hsa}, ratio={ratio} → {result}"

    #
    # test_overlap_ratio_affects_result
    #
    def test_overlap_ratio_affects_result(self) -> None:
        """Lower d/L ratio (more overlap) should allow more open tilt."""

        tight = CoverAutomation._calculate_auto_tilt(30, 0, 0.7)
        loose = CoverAutomation._calculate_auto_tilt(30, 0, 0.95)
        assert tight > loose  # More overlap = larger tilt%

    #
    # test_sun_parallel_to_facade
    #
    def test_sun_parallel_to_facade(self) -> None:
        """Sun nearly parallel to facade (azimuth diff ~90°) should handle gracefully."""

        result = CoverAutomation._calculate_auto_tilt(30, 89, 0.9)
        assert 0 <= result <= 100

    #
    # test_sun_exactly_parallel_to_facade
    #
    def test_sun_exactly_parallel_to_facade(self) -> None:
        """Sun exactly parallel to facade (HSA=90°) triggers the cos(HSA)≈0 guard."""

        # cos(90°) ≈ 6e-17 which is below the 1e-10 threshold,
        # so omega_rad is set to π/2 instead of computing atan(tan/0).
        result = CoverAutomation._calculate_auto_tilt(30, 90, 0.9)
        assert 0 <= result <= 100

    #
    # test_ratio_exceeds_unity_fully_closes
    #
    def test_ratio_exceeds_unity_fully_closes(self) -> None:
        """When slat_overlap_ratio * cos(omega) > 1, geometry is impossible → fully close."""

        # With d/L=1.5 and low elevation (5°, HSA=0°): omega≈5°, cos(omega)≈0.996,
        # ratio = 1.5 * 0.996 ≈ 1.49 > 1 → theta_deg = 90 → tilt = 0%.
        result = CoverAutomation._calculate_auto_tilt(5, 0, 1.5)
        assert result == 0


# ───────────────────────────────────────────────────────────────────────
# Tilt mode resolution tests
# ───────────────────────────────────────────────────────────────────────


class TestGetEffectiveTiltMode:
    """Tests for _get_effective_tilt_mode."""

    #
    # test_returns_none_when_no_tilt_support
    #
    def test_returns_none_when_no_tilt_support(
        self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger
    ) -> None:
        """Covers without tilt support should return None."""

        config = {"cover.test_cover_azimuth": 180.0}
        auto = _make_automation(mock_resolved_config, config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = False
        assert auto._get_effective_tilt_mode(is_night=False) is None

    #
    # test_returns_global_day_mode
    #
    def test_returns_global_day_mode(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger) -> None:
        """Should return global day tilt mode when no per-cover override."""

        config = {"cover.test_cover_azimuth": 180.0}
        mock_resolved_config.tilt_mode_day = TiltMode.AUTO
        auto = _make_automation(mock_resolved_config, config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True
        assert auto._get_effective_tilt_mode(is_night=False) == TiltMode.AUTO

    #
    # test_returns_global_night_mode
    #
    def test_returns_global_night_mode(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger) -> None:
        """Should return global night tilt mode when no per-cover override."""

        config = {"cover.test_cover_azimuth": 180.0}
        mock_resolved_config.tilt_mode_night = TiltMode.OPEN
        auto = _make_automation(mock_resolved_config, config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True
        assert auto._get_effective_tilt_mode(is_night=True) == TiltMode.OPEN

    #
    # test_per_cover_override_day
    #
    def test_per_cover_override_day(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger) -> None:
        """Per-cover day override takes precedence over global."""

        config = {
            "cover.test_cover_azimuth": 180.0,
            "cover.test_cover_tilt_mode_day": TiltMode.MANUAL,
        }
        mock_resolved_config.tilt_mode_day = TiltMode.OPEN
        auto = _make_automation(mock_resolved_config, config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True
        assert auto._get_effective_tilt_mode(is_night=False) == TiltMode.MANUAL

    #
    # test_per_cover_override_night
    #
    def test_per_cover_override_night(self, mock_resolved_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger) -> None:
        """Per-cover night override takes precedence over global."""

        config = {
            "cover.test_cover_azimuth": 180.0,
            "cover.test_cover_tilt_mode_night": TiltMode.OPEN,
        }
        mock_resolved_config.tilt_mode_night = TiltMode.CLOSED
        auto = _make_automation(mock_resolved_config, config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True
        assert auto._get_effective_tilt_mode(is_night=True) == TiltMode.OPEN


# ───────────────────────────────────────────────────────────────────────
# Tilt application tests
# ───────────────────────────────────────────────────────────────────────


class TestApplyTilt:
    """Tests for _apply_tilt method."""

    #
    # test_skips_tilt_when_cover_fully_open_no_movement
    #
    @pytest.mark.asyncio
    async def test_skips_tilt_when_cover_fully_open_no_movement(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Tilt should be skipped when cover is fully open (raised) and did not move."""

        mock_resolved_config.tilt_mode_day = TiltMode.OPEN
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        cover_state = CoverState(pos_current=100, tilt_current=50, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, False)

        mock_ha_interface.set_cover_tilt_position.assert_not_called()
        assert cover_state.tilt_target is None

    #
    # test_skips_tilt_when_cover_moved_to_fully_open
    #
    @pytest.mark.asyncio
    async def test_skips_tilt_when_cover_moved_to_fully_open(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Tilt should be skipped when cover was moved to fully open (raised)."""

        mock_resolved_config.tilt_mode_day = TiltMode.OPEN
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        cover_state = CoverState(pos_target_final=100, tilt_current=50, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, True)

        mock_ha_interface.set_cover_tilt_position.assert_not_called()
        assert cover_state.tilt_target is None

    #
    # test_open_mode_sets_tilt_100
    #
    @pytest.mark.asyncio
    async def test_open_mode_sets_tilt_100(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Open tilt mode should set tilt to 100 (horizontal)."""

        mock_resolved_config.tilt_mode_day = TiltMode.OPEN
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        cover_state = CoverState(tilt_current=50, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, True)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 100, tilt_features)
        assert cover_state.tilt_target == 100

    #
    # test_closed_mode_sets_tilt_0
    #
    @pytest.mark.asyncio
    async def test_closed_mode_sets_tilt_0(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Closed tilt mode should set tilt to 0 (vertical)."""

        mock_resolved_config.tilt_mode_day = TiltMode.CLOSED
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=0)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        cover_state = CoverState(tilt_current=50, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.CLOSING_HEAT_PROTECTION, True)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 0, tilt_features)
        assert cover_state.tilt_target == 0

    #
    # test_manual_mode_restores_pre_move_tilt
    #
    @pytest.mark.asyncio
    async def test_manual_mode_restores_pre_move_tilt(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Manual mode should restore the tilt that was read before the cover moved."""

        mock_resolved_config.tilt_mode_day = TiltMode.MANUAL
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=75)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        # tilt_current=75 is the pre-move snapshot read from HA state before position change
        cover_state = CoverState(tilt_current=75, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, True)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 75, tilt_features)
        assert cover_state.tilt_target == 75

    #
    # test_manual_mode_uses_current_tilt_each_cycle
    #
    @pytest.mark.asyncio
    async def test_manual_mode_uses_current_tilt_each_cycle(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Manual mode should use the current tilt snapshot each cycle, not a cached value."""

        mock_resolved_config.tilt_mode_day = TiltMode.MANUAL
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        # First cycle: user had tilt at 75
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=75)
        cover_state1 = CoverState(tilt_current=75, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state1, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, True)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 75, tilt_features)

        # Second cycle: user changed tilt to 30 between cycles
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=30)
        cover_state2 = CoverState(tilt_current=30, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state2, sensor_data, tilt_features, CoverMovementReason.CLOSING_HEAT_PROTECTION, True)

        # Should restore 30, not 75 from the first cycle
        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 30, tilt_features)

    #
    # test_manual_mode_skips_when_no_tilt_info
    #
    @pytest.mark.asyncio
    async def test_manual_mode_skips_when_no_tilt_info(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Manual mode should skip tilt when current tilt info is unavailable."""

        mock_resolved_config.tilt_mode_day = TiltMode.MANUAL
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        cover_state = CoverState(tilt_current=None, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, True)

        mock_ha_interface.set_cover_tilt_position.assert_not_called()

    #
    # test_auto_mode_calculates_tilt_from_sun
    #
    @pytest.mark.asyncio
    async def test_auto_mode_calculates_tilt_from_sun(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features
    ) -> None:
        """Auto mode should calculate tilt using the physics formula."""

        mock_resolved_config.tilt_mode_day = TiltMode.AUTO
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=58)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        data = SensorData(
            sun_azimuth=180.0,
            sun_elevation=20.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=False,
            post_evening_closure=False,
        )
        cover_state = CoverState(tilt_current=100, sun_hitting=True, sun_azimuth_diff=0.0)
        await auto._apply_tilt(cover_state, data, tilt_features, CoverMovementReason.CLOSING_HEAT_PROTECTION, True)

        # Verify set_cover_tilt_position was called with a value in the expected range
        call_args = mock_ha_interface.set_cover_tilt_position.call_args
        assert call_args is not None
        tilt_value = call_args[0][1]
        assert 55 <= tilt_value <= 62  # ~58% expected

    #
    # test_set_value_mode_uses_configured_angle
    #
    @pytest.mark.asyncio
    async def test_set_value_mode_uses_configured_angle(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Set value mode at night should use the configured night tilt angle."""

        mock_resolved_config.tilt_mode_night = TiltMode.SET_VALUE
        mock_resolved_config.tilt_set_value_night = 30
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=30)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        cover_state = CoverState(tilt_current=50, sun_hitting=False, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.CLOSING_AFTER_SUNSET, True)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 30, tilt_features)

    #
    # test_set_value_day_mode_uses_configured_day_angle
    #
    @pytest.mark.asyncio
    async def test_set_value_day_mode_uses_configured_day_angle(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Set value mode during the day should use the configured day tilt angle."""

        mock_resolved_config.tilt_mode_day = TiltMode.SET_VALUE
        mock_resolved_config.tilt_set_value_day = 65
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=65)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        cover_state = CoverState(tilt_current=50, sun_hitting=True, sun_azimuth_diff=10.0)
        # Not a sunset closure → daytime context
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.CLOSING_HEAT_PROTECTION, True)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 65, tilt_features)

    #
    # test_auto_mode_opens_when_sun_not_hitting
    #
    @pytest.mark.asyncio
    async def test_auto_mode_opens_when_sun_not_hitting(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Auto mode should set tilt to 100 when sun is not hitting the window."""

        mock_resolved_config.tilt_mode_day = TiltMode.AUTO
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        cover_state = CoverState(tilt_current=50, sun_hitting=False, sun_azimuth_diff=90.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, True)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 100, tilt_features)

    #
    # test_auto_mode_opens_when_not_sunny
    #
    @pytest.mark.asyncio
    async def test_auto_mode_opens_when_not_sunny(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Auto mode should set tilt to 100 when weather is not sunny (overcast)."""

        mock_resolved_config.tilt_mode_day = TiltMode.AUTO
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        # Sun IS hitting geometrically, but weather is not sunny
        sensor_data.weather_sunny = False
        cover_state = CoverState(tilt_current=50, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, True)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 100, tilt_features)

    #
    # test_no_tilt_when_cover_doesnt_support
    #
    @pytest.mark.asyncio
    async def test_no_tilt_when_cover_doesnt_support(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, sensor_data
    ) -> None:
        """Covers without tilt support should not receive tilt commands."""

        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = False

        features = CoverEntityFeature.SET_POSITION  # No tilt
        cover_state = CoverState()
        await auto._apply_tilt(cover_state, sensor_data, features, CoverMovementReason.OPENING_LET_LIGHT_IN, True)

        mock_ha_interface.set_cover_tilt_position.assert_not_called()
        assert cover_state.tilt_target is None

    #
    # test_delta_threshold_prevents_small_changes
    #
    @pytest.mark.asyncio
    async def test_delta_threshold_prevents_small_changes(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Changes smaller than tilt_min_change_delta should be skipped (when cover didn't move)."""

        mock_resolved_config.tilt_mode_day = TiltMode.OPEN
        mock_resolved_config.tilt_min_change_delta = 10
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        # Current tilt is 95, target is 100 — delta is 5, below threshold of 10
        cover_state = CoverState(tilt_current=95, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, False)

        mock_ha_interface.set_cover_tilt_position.assert_not_called()

    #
    # test_delta_threshold_bypassed_when_cover_moved
    #
    @pytest.mark.asyncio
    async def test_delta_threshold_bypassed_when_cover_moved(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Delta threshold should be bypassed when cover position just changed."""

        mock_resolved_config.tilt_mode_day = TiltMode.OPEN
        mock_resolved_config.tilt_min_change_delta = 10
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        # Current tilt is 95, target is 100 — delta is 5, below threshold
        # But cover_moved=True, so tilt should still be applied
        cover_state = CoverState(tilt_current=95, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, True)

        mock_ha_interface.set_cover_tilt_position.assert_called_once()

    #
    # test_delta_zero_always_sends_updates
    #
    @pytest.mark.asyncio
    async def test_delta_zero_always_sends_updates(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features, sensor_data
    ) -> None:
        """Delta threshold of 0 should always send tilt updates."""

        mock_resolved_config.tilt_mode_day = TiltMode.OPEN
        mock_resolved_config.tilt_min_change_delta = 0
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)
        auto._cover_supports_tilt = True

        # Even tiny change should trigger update when delta=0
        cover_state = CoverState(tilt_current=99, sun_hitting=True, sun_azimuth_diff=10.0)
        await auto._apply_tilt(cover_state, sensor_data, tilt_features, CoverMovementReason.OPENING_LET_LIGHT_IN, False)

        mock_ha_interface.set_cover_tilt_position.assert_called_once()


# ───────────────────────────────────────────────────────────────────────
# Process integration tests (tilt within full flow)
# ───────────────────────────────────────────────────────────────────────


class TestProcessWithTilt:
    """Tests for tilt handling within the process() method."""

    #
    # test_process_reads_current_tilt
    #
    @pytest.mark.asyncio
    async def test_process_reads_current_tilt(
        self,
        mock_resolved_config,
        basic_config,
        mock_cover_pos_history_mgr,
        mock_ha_interface,
        mock_logger,
        tilt_features,
        sensor_data,
        mock_state,
    ) -> None:
        """Process should read current tilt position from cover state."""

        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        cover_state = await auto.process(mock_state, sensor_data)

        assert cover_state.tilt_current == 50  # From mock_state fixture

    #
    # test_process_applies_tilt_after_position_move
    #
    @pytest.mark.asyncio
    async def test_process_applies_tilt_after_position_move(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features
    ) -> None:
        """Process should apply tilt after position change."""

        mock_resolved_config.tilt_mode_day = TiltMode.OPEN
        mock_ha_interface.set_cover_position = AsyncMock(return_value=0)
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)

        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        # Create state for heat protection scenario (cover currently open, needs to close)
        state = MagicMock()
        state.state = STATE_OPEN
        state.attributes = {
            ATTR_CURRENT_POSITION: 100,
            ATTR_CURRENT_TILT_POSITION: 50,
            "supported_features": tilt_features,
        }
        data = SensorData(
            sun_azimuth=180.0,
            sun_elevation=45.0,
            temp_max=30.0,
            temp_hot=True,
            weather_condition="sunny",
            weather_sunny=True,
            evening_closure=False,
            post_evening_closure=False,
        )

        cover_state = await auto.process(state, data)

        # Should have called both position and tilt
        mock_ha_interface.set_cover_position.assert_called_once()
        mock_ha_interface.set_cover_tilt_position.assert_called_once()
        assert cover_state.tilt_target == 100

    #
    # test_process_applies_night_tilt_during_evening_closure_when_opening_block_enabled
    #
    @pytest.mark.asyncio
    async def test_process_applies_night_tilt_during_evening_closure_when_opening_block_enabled(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, tilt_features
    ) -> None:
        """Evening closure should still apply night tilt when the post-closure opening block is enabled."""

        mock_resolved_config.block_opening_after_evening_closure = True
        mock_resolved_config.evening_closure_enabled = True
        mock_resolved_config.evening_closure_cover_list = ("cover.test",)
        mock_resolved_config.tilt_mode_night = TiltMode.SET_VALUE
        mock_resolved_config.tilt_set_value_night = 30
        mock_ha_interface.set_cover_position = AsyncMock(return_value=0)
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=30)

        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        state = MagicMock()
        state.state = STATE_OPEN
        state.attributes = {
            ATTR_CURRENT_POSITION: 50,
            ATTR_CURRENT_TILT_POSITION: 100,
            "supported_features": tilt_features,
        }
        data = SensorData(
            sun_azimuth=180.0,
            sun_elevation=10.0,
            temp_max=20.0,
            temp_hot=False,
            weather_condition="cloudy",
            weather_sunny=False,
            evening_closure=True,
            post_evening_closure=True,
        )

        cover_state = await auto.process(state, data)

        mock_ha_interface.set_cover_position.assert_called_once_with("cover.test", 0, tilt_features)
        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 30, tilt_features)
        assert cover_state.tilt_target == 30

    #
    # test_process_no_tilt_for_position_only_covers
    #
    @pytest.mark.asyncio
    async def test_process_no_tilt_for_position_only_covers(
        self, mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger, sensor_data
    ) -> None:
        """Process should not set tilt for covers that only support position."""

        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        state = MagicMock()
        state.state = STATE_OPEN
        state.attributes = {
            ATTR_CURRENT_POSITION: 100,
            "supported_features": CoverEntityFeature.SET_POSITION,  # No tilt
        }

        cover_state = await auto.process(state, sensor_data)

        mock_ha_interface.set_cover_tilt_position.assert_not_called()
        assert cover_state.tilt_current is None

    #
    # test_tilt_error_does_not_break_process
    #
    @pytest.mark.asyncio
    async def test_tilt_error_does_not_break_process(
        self,
        mock_resolved_config,
        basic_config,
        mock_cover_pos_history_mgr,
        mock_ha_interface,
        mock_logger,
        tilt_features,
        sensor_data,
        mock_state,
    ) -> None:
        """Tilt service errors should be logged but not crash the process."""

        mock_resolved_config.tilt_mode_day = TiltMode.OPEN
        mock_ha_interface.set_cover_tilt_position = AsyncMock(side_effect=Exception("Tilt service error"))
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        # Should not raise
        cover_state = await auto.process(mock_state, sensor_data)
        assert cover_state is not None


# ───────────────────────────────────────────────────────────────────────
# Lock mode tilt tests
# ───────────────────────────────────────────────────────────────────────


class TestLockModeTilt:
    """Tests for tilt behavior during lock modes."""

    #
    # test_force_open_sets_tilt_100
    #
    @pytest.mark.asyncio
    async def test_force_open_sets_tilt_100(
        self,
        mock_resolved_config,
        basic_config,
        mock_cover_pos_history_mgr,
        mock_ha_interface,
        mock_logger,
        tilt_features,
        sensor_data,
        mock_state,
    ) -> None:
        """FORCE_OPEN lock should set tilt to 100."""

        mock_resolved_config.lock_mode = LockMode.FORCE_OPEN
        mock_ha_interface.set_cover_position = AsyncMock(return_value=100)
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=100)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        cover_state = await auto.process(mock_state, sensor_data)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 100, tilt_features)
        assert cover_state.tilt_target == 100

    #
    # test_force_close_sets_tilt_0
    #
    @pytest.mark.asyncio
    async def test_force_close_sets_tilt_0(
        self,
        mock_resolved_config,
        basic_config,
        mock_cover_pos_history_mgr,
        mock_ha_interface,
        mock_logger,
        tilt_features,
        sensor_data,
        mock_state,
    ) -> None:
        """FORCE_CLOSE lock should set tilt to 0."""

        mock_resolved_config.lock_mode = LockMode.FORCE_CLOSE
        mock_ha_interface.set_cover_position = AsyncMock(return_value=0)
        mock_ha_interface.set_cover_tilt_position = AsyncMock(return_value=0)
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        # Cover starts at position 50 with tilt 50
        state = MagicMock()
        state.state = STATE_OPEN
        state.attributes = {
            ATTR_CURRENT_POSITION: 50,
            ATTR_CURRENT_TILT_POSITION: 50,
            "supported_features": tilt_features,
        }

        cover_state = await auto.process(state, sensor_data)

        mock_ha_interface.set_cover_tilt_position.assert_called_once_with("cover.test", 0, tilt_features)
        assert cover_state.tilt_target == 0

    #
    # test_force_open_tilt_error_is_caught
    #
    @pytest.mark.asyncio
    async def test_force_open_tilt_error_is_caught(
        self,
        mock_resolved_config,
        basic_config,
        mock_cover_pos_history_mgr,
        mock_ha_interface,
        mock_logger,
        tilt_features,
        sensor_data,
        mock_state,
    ) -> None:
        """FORCE_OPEN lock should catch tilt errors and continue without crashing."""

        mock_resolved_config.lock_mode = LockMode.FORCE_OPEN
        mock_ha_interface.set_cover_position = AsyncMock(return_value=100)
        mock_ha_interface.set_cover_tilt_position = AsyncMock(side_effect=RuntimeError("Tilt failed"))
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        # Should not raise — error is caught and logged
        cover_state = await auto.process(mock_state, sensor_data)

        mock_logger.error.assert_called()
        assert cover_state is not None

    #
    # test_force_close_tilt_error_is_caught
    #
    @pytest.mark.asyncio
    async def test_force_close_tilt_error_is_caught(
        self,
        mock_resolved_config,
        basic_config,
        mock_cover_pos_history_mgr,
        mock_ha_interface,
        mock_logger,
        tilt_features,
        sensor_data,
    ) -> None:
        """FORCE_CLOSE lock should catch tilt errors and continue without crashing."""

        mock_resolved_config.lock_mode = LockMode.FORCE_CLOSE
        mock_ha_interface.set_cover_position = AsyncMock(return_value=0)
        mock_ha_interface.set_cover_tilt_position = AsyncMock(side_effect=RuntimeError("Tilt failed"))
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        state = MagicMock()
        state.state = STATE_OPEN
        state.attributes = {
            ATTR_CURRENT_POSITION: 50,
            ATTR_CURRENT_TILT_POSITION: 50,
            "supported_features": tilt_features,
        }

        # Should not raise — error is caught and logged
        cover_state = await auto.process(state, sensor_data)

        mock_logger.error.assert_called()
        assert cover_state is not None

    #
    # test_hold_position_skips_tilt
    #
    @pytest.mark.asyncio
    async def test_hold_position_skips_tilt(
        self,
        mock_resolved_config,
        basic_config,
        mock_cover_pos_history_mgr,
        mock_ha_interface,
        mock_logger,
        tilt_features,
        sensor_data,
        mock_state,
    ) -> None:
        """HOLD_POSITION lock should not send any tilt commands."""

        mock_resolved_config.lock_mode = LockMode.HOLD_POSITION
        auto = _make_automation(mock_resolved_config, basic_config, mock_cover_pos_history_mgr, mock_ha_interface, mock_logger)

        await auto.process(mock_state, sensor_data)

        mock_ha_interface.set_cover_tilt_position.assert_not_called()
