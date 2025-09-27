"""Combined automation logic tests.

This module contains comprehensive tests for the combined temperature and sun
automation logic in the DataUpdateCoordinator, including AND logic scenarios,
multi-cover configurations, and threshold boundary conditions.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES, Platform

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_SFX_AZIMUTH,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_WEATHER_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COMFORTABLE_TEMP_2,
    TEST_COVER_CLOSED,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    TEST_INDIRECT_AZIMUTH,
    MockConfigEntry,
    create_combined_state_mock,
    create_sun_config,
    set_weather_forecast_temp,
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestCombinedAutomation(TestDataUpdateCoordinatorBase):
    """Test suite for combined temperature and sun automation logic."""

    @pytest.mark.parametrize(
        "sun_azimuth,cover_east_expected,cover_south_expected,cover_west_expected,time_description",
        [
            # Sun positions through the day - azimuth tolerance is 90° (difference must be < 90°)
            # East cover: 90°, South cover: 180°, West cover: 270°
            # Early morning: Sun at 60° - only east cover within tolerance (30° diff)
            (60, 0, 100, 100, "Early morning - Sun at 60°, only east cover closes"),
            # Morning: Sun at 90° - only east cover within tolerance (0° diff)
            (90, 0, 100, 100, "Morning - Sun at 90°, only east cover closes"),
            # Late morning: Sun at 120° - east (30° diff) and south (60° diff) within tolerance
            (120, 0, 0, 100, "Late morning - Sun at 120°, east and south covers close"),
            # Midday: Sun at 180° - only south cover within tolerance (0° diff)
            (180, 100, 0, 100, "Midday - Sun at 180°, only south cover closes"),
            # Afternoon: Sun at 210° - south (30° diff) and west (60° diff) within tolerance
            (210, 100, 0, 0, "Afternoon - Sun at 210°, south and west covers close"),
            # Evening: Sun at 270° - only west cover within tolerance (0° diff)
            (270, 100, 100, 0, "Evening - Sun at 270°, only west cover closes"),
            # Late evening: Sun at 330° - east (60° diff via wrapping) and west (60° diff) close
            (330, 100, 100, 0, "Late evening - Sun at 330°, only west cover closes"),
        ],
    )
    @pytest.mark.asyncio
    async def test_sun_automation_daily_movement_multiple_covers(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        sun_azimuth: float,
        cover_east_expected: int,
        cover_south_expected: int,
        cover_west_expected: int,
        time_description: str,
    ) -> None:
        """Test multiple covers with different orientations throughout sun's daily path.

        Simulates the sun's movement from east to west during a day and validates
        that only covers facing the sun close while others remain open. This tests
        the azimuth tolerance logic with realistic sun positions and multiple cover
        orientations representing typical building layouts.

        Cover orientations:
        - East cover: 90° (morning sun)
        - South cover: 180° (midday sun)
        - West cover: 270° (evening sun)

        Expected behavior:
        - Only covers within azimuth tolerance of sun position should close
        - Covers not facing sun should open to maximum position
        - Transition periods show gradual handoff between covers
        """
        # Set weather forecast temperature to hot for this test
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        # Create covers facing different directions (east, south, west)
        east_cover = "cover.east_window"
        south_cover = "cover.south_window"
        west_cover = "cover.west_window"

        config = create_sun_config(covers=[east_cover, south_cover, west_cover])
        config[f"{east_cover}_{COVER_SFX_AZIMUTH}"] = 90  # East-facing
        config[f"{south_cover}_{COVER_SFX_AZIMUTH}"] = 180  # South-facing
        config[f"{west_cover}_{COVER_SFX_AZIMUTH}"] = 270  # West-facing
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Setup cover states - all start open
        cover_states = {}
        for cover_id in [east_cover, south_cover, west_cover]:
            cover_states[cover_id] = {
                ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
                ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
            }

        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": sun_azimuth}
        state_mapping = create_combined_state_mock(
            sun_azimuth=sun_azimuth,
            cover_states=cover_states,
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        covers = coordinator.data[ConfKeys.COVERS.value]

        # Validate expected positions for each cover
        assert covers[east_cover]["sca_cover_desired_position"] == cover_east_expected, (
            f"{time_description}: East cover (90°) with sun at {sun_azimuth}° - "
            f"Expected {cover_east_expected}, got {covers[east_cover]['sca_cover_desired_position']}"
        )

        assert covers[south_cover]["sca_cover_desired_position"] == cover_south_expected, (
            f"{time_description}: South cover (180°) with sun at {sun_azimuth}° - "
            f"Expected {cover_south_expected}, got {covers[south_cover]['sca_cover_desired_position']}"
        )

        assert covers[west_cover]["sca_cover_desired_position"] == cover_west_expected, (
            f"{time_description}: West cover (270°) with sun at {sun_azimuth}° - "
            f"Expected {cover_west_expected}, got {covers[west_cover]['sca_cover_desired_position']}"
        )

    @pytest.mark.asyncio
    async def test_sun_automation_threshold_equality_uses_closure(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that sun elevation exactly at threshold triggers closure logic.

        Validates that when the sun elevation equals the configured threshold,
        the automation treats it as "above threshold" and applies closure logic
        when combined with appropriate temperature and azimuth conditions.

        Test scenario:
        - Sun elevation: 20.0° (exactly at threshold)
        - Sun azimuth: 180° (direct hit)
        - Temperature: Hot (supports closure)
        - Expected: Covers close (threshold equality treated as above)
        """
        # Set weather forecast temperature to hot for this test
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = TEST_DIRECT_AZIMUTH
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        # Elevation equals threshold (20.0); should treat as above for logic
        mock_sun_state.attributes = {"elevation": 20.0, "azimuth": TEST_DIRECT_AZIMUTH}

        state_mapping = create_combined_state_mock(
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Sun hitting directly (angle_diff = 0 = threshold)
            cover_states={MOCK_COVER_ENTITY_ID: cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_CLOSED

    @pytest.mark.parametrize(
        "sun_azimuth,max_closure,min_closure,expected_position,test_description",
        [
            # Direct sun hit scenarios
            (TEST_DIRECT_AZIMUTH, 0, 100, 0, "Direct sun, full closure allowed"),
            (TEST_DIRECT_AZIMUTH, 20, 100, 20, "Direct sun, limited max closure"),
            (TEST_DIRECT_AZIMUTH, 50, 100, 50, "Direct sun, moderate max closure"),
            (TEST_DIRECT_AZIMUTH, 0, 80, 0, "Direct sun, min closure limit ignored when closing"),
            (TEST_DIRECT_AZIMUTH, 30, 70, 30, "Direct sun, max closure within min range"),
            # Indirect sun scenarios (sun not hitting window)
            (TEST_INDIRECT_AZIMUTH, 0, 100, 100, "Indirect sun, full opening allowed"),
            (TEST_INDIRECT_AZIMUTH, 20, 100, 100, "Indirect sun, max closure irrelevant"),
            (TEST_INDIRECT_AZIMUTH, 50, 80, 80, "Indirect sun, min closure enforced"),
            (TEST_INDIRECT_AZIMUTH, 0, 60, 60, "Indirect sun, min closure limits opening"),
            (TEST_INDIRECT_AZIMUTH, 30, 40, 40, "Indirect sun, min closure tighter than max"),
        ],
    )
    @pytest.mark.asyncio
    async def test_sun_automation_closure_position_matrix(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        sun_azimuth: float,
        max_closure: int,
        min_closure: int,
        expected_position: int,
        test_description: str,
    ) -> None:
        """Test closure position matrix with various sun positions and min/max settings.

        Validates that the automation correctly applies min/max closure limits based on
        sun position and configuration. When sun hits directly, max_closure limits how
        much covers close. When sun doesn't hit, min_closure limits how much covers open.

        Test matrix covers:
        - Direct sun hits with various max_closure limits
        - Indirect sun with various min_closure limits
        - Edge cases where min/max ranges overlap
        - Full closure/opening boundary conditions
        """
        # Set weather forecast temperature to hot for direct sun scenarios
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config[ConfKeys.COVERS_MAX_CLOSURE.value] = max_closure
        config[ConfKeys.COVERS_MIN_CLOSURE.value] = min_closure
        config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = TEST_DIRECT_AZIMUTH
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": sun_azimuth}

        state_mapping = create_combined_state_mock(
            sun_azimuth=sun_azimuth,
            cover_states={MOCK_COVER_ENTITY_ID: cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]

        assert cover_data["sca_cover_desired_position"] == expected_position, (
            f"Test case: {test_description}\n"
            f"Sun azimuth: {sun_azimuth}, Max closure: {max_closure}, Min closure: {min_closure}\n"
            f"Expected: {expected_position}, Got: {cover_data['sca_cover_desired_position']}"
        )

    @pytest.mark.asyncio
    async def test_combined_hot_sun_not_hitting_no_change_with_and_logic(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test AND logic when temperature is hot but sun not hitting window.

        Validates that the combined automation uses AND logic, requiring both
        hot temperature AND sun hitting the window to trigger cover closure.
        When only one condition is met, covers should remain open.

        Test scenario:
        - Temperature: Hot (26°C, above threshold)
        - Sun elevation: High (above threshold)
        - Sun azimuth: Not hitting window (90° vs 180° window)
        - Expected: No cover movement (AND condition not fully satisfied)
        """
        # Set weather forecast temperature to hot for this test
        set_weather_forecast_temp(float(mock_temperature_state.state))

        config = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: 24.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}": TEST_DIRECT_AZIMUTH,
        }
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Too hot; sun above threshold but azimuth far from window direction
        mock_temperature_state.state = TEST_HOT_TEMP
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_INDIRECT_AZIMUTH}
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            sun_azimuth=TEST_INDIRECT_AZIMUTH,  # Sun azimuth far from window direction (180°)
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN
        # AND semantics: no action when sun not hitting - verify no cover service calls
        cover_calls = [call for call in mock_hass.services.async_call.call_args_list if call[0][0] != Platform.WEATHER]
        assert len(cover_calls) == 0, f"Expected no cover service calls, got: {cover_calls}"

    @pytest.mark.asyncio
    async def test_combined_comfortable_direct_sun_no_change_with_and_logic(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test AND logic when temperature is comfortable but sun hitting window.

        Validates that comfortable temperature with direct sun doesn't trigger
        cover closure because the AND logic requires hot temperature AND sun
        hitting to trigger the closure action.

        Test scenario:
        - Temperature: Comfortable (22.5°C, within range)
        - Sun elevation: High (above threshold)
        - Sun azimuth: Direct hit (180° matching window)
        - Expected: No cover movement (temperature not hot enough)
        """
        # Set weather forecast temperature to comfortable for this test
        set_weather_forecast_temp(float(mock_temperature_state.state))

        config = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: 24.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 60,  # partial closure
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}": TEST_DIRECT_AZIMUTH,
        }
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_temperature_state.state = TEST_COMFORTABLE_TEMP_2
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN
        # No action when temperature is not hot - verify no cover service calls
        cover_calls = [call for call in mock_hass.services.async_call.call_args_list if call[0][0] != Platform.WEATHER]
        assert len(cover_calls) == 0, f"Expected no cover service calls, got: {cover_calls}"

    @pytest.mark.asyncio
    async def test_combined_cold_direct_sun_no_change_with_and_logic(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test AND logic when temperature is cold but sun hitting window.

        Validates that cold temperature with direct sun doesn't trigger cover
        closure. In fact, cold temperature should favor opening covers for
        warmth, regardless of sun position.

        Test scenario:
        - Temperature: Cold (18°C, below minimum)
        - Sun elevation: High (above threshold)
        - Sun azimuth: Direct hit (180° matching window)
        - Expected: No cover movement (cold temp wants open, not close)
        """
        # Set weather forecast temperature to cold for this test
        set_weather_forecast_temp(float(mock_temperature_state.state))

        config = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: 24.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}": TEST_DIRECT_AZIMUTH,
        }
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_temperature_state.state = TEST_COLD_TEMP
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN
        # AND semantics: no action when temperature is cold - verify no cover service calls
        cover_calls = [call for call in mock_hass.services.async_call.call_args_list if call[0][0] != Platform.WEATHER]
        assert len(cover_calls) == 0, f"Expected no cover service calls, got: {cover_calls}"

    @pytest.mark.asyncio
    async def test_combined_missing_direction_uses_temp_only(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        mock_cover_state: MagicMock,
        mock_temperature_state: MagicMock,
    ) -> None:
        """Test behavior when sun direction configuration is missing.

        Validates that covers without sun direction configuration are excluded
        from combined automation processing, even when temperature conditions
        would normally trigger actions. This ensures proper configuration
        validation and error handling.

        Test scenario:
        - Temperature: Hot (would normally trigger closure)
        - Sun: Direct conditions available
        - Cover configuration: Missing direction/azimuth setting
        - Expected: Cover skipped from automation (missing config)
        """
        # Set weather forecast temperature to hot for this test
        set_weather_forecast_temp(float(mock_temperature_state.state))

        config = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.TEMP_THRESHOLD.value: 24.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            # Intentionally omit direction key
        }
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_temperature_state.state = TEST_HOT_TEMP
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Cover should be skipped due to missing direction, even in combined mode
        assert MOCK_COVER_ENTITY_ID not in result[ConfKeys.COVERS.value]
