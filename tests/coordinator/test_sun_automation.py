"""Sun-based automation tests.

This module contains comprehensive tests for sun-based automation logic
in the DataUpdateCoordinator, including sun elevation, azimuth calculations,
window orientation handling, and error conditions related to sun sensors.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from homeassistant.components.cover import ATTR_CURRENT_POSITION, CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_ATTR_SUN_AZIMUTH_DIFF,
    COVER_ATTR_SUN_HITTING,
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
    SENSOR_ATTR_TEMP_HOT,
)
from custom_components.smart_cover_automation.coordinator import (
    DataUpdateCoordinator,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_COVER_ENTITY_ID_2,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COMFORTABLE_TEMP_1,
    TEST_COVER_CLOSED,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    TEST_INDIRECT_AZIMUTH,
    TEST_LOW_ELEVATION,
    TEST_PARTIAL_POSITION,
    MockConfigEntry,
    create_combined_state_mock,
    create_sun_config,
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestSunAutomation(TestDataUpdateCoordinatorBase):
    """Test suite for sun-based automation logic."""

    async def test_sun_automation_direct_sun(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test sun-based automation when sun is directly hitting the window.

        Validates that the automation correctly closes covers when the sun is at
        high elevation and positioned to directly hit the configured window orientation.
        This test simulates midday conditions where covers should close to block
        direct sunlight and heat.

        Test scenario:
        - Sun elevation: 45° (above 20° threshold)
        - Sun azimuth: 180° (directly hitting south-facing window)
        - Temperature: 25°C (hot, supporting cover closure in combined logic)
        - Current cover position: Fully open (100)
        - Expected action: Close covers to 0 to block direct sun
        """
        # Setup cover in open position receiving direct sunlight
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        # Create environmental state: direct sun + hot temperature
        state_mapping = create_combined_state_mock(
            temp_state="25.0",  # Hot for AND logic
            sun_elevation=TEST_HIGH_ELEVATION,
            sun_azimuth=TEST_DIRECT_AZIMUTH,
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute sun automation logic
        await sun_coordinator.async_refresh()
        result = sun_coordinator.data

        # Verify sun automation closes covers due to direct sunlight
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result["sun_elevation"] == TEST_HIGH_ELEVATION
        assert result["sun_azimuth"] == TEST_DIRECT_AZIMUTH
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_CLOSED

    async def test_sun_automation_respects_max_closure_option(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that sun automation respects the configured maximum closure percentage.

        Validates that when direct sunlight hits the window, the automation uses the
        configured `covers_max_closure` setting instead of fully closing the covers.
        This allows users to block most sunlight while still maintaining some visibility
        and natural light.

        Test scenario:
        - Sun elevation: 45° (above threshold)
        - Sun azimuth: 180° (direct hit)
        - Configuration: covers_max_closure = 60% (instead of default 100%)
        - Expected action: Close covers to 60% (not fully closed)
        """
        # Create configuration with custom maximum closure setting
        config = create_sun_config()
        config[ConfKeys.COVERS_MAX_CLOSURE.value] = 60  # cap direct hit to 60%
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Setup sun directly hitting window
        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_DIRECT_AZIMUTH,
        }
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        # With covers_max_closure=60 and direct hit, desired = 100 - 60 = 40
        assert cover_data["sca_cover_desired_position"] == COVER_POS_FULLY_OPEN

    async def test_sun_automation_low_sun(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test sun automation with low sun elevation.

        Validates that when the sun is below the elevation threshold, the sun automation
        doesn't trigger closure logic regardless of azimuth alignment. This prevents
        covers from closing during early morning or late evening when the sun doesn't
        contribute significant heat.

        Test scenario:
        - Sun elevation: 15° (below 20° threshold)
        - Sun azimuth: 180° (would be direct hit if elevation was sufficient)
        - Temperature: 18°C (cold, supports opening)
        - Expected action: Open covers (low sun doesn't trigger closure)
        """
        # Setup - sun below threshold
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_PARTIAL_POSITION

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp wants open
            sun_elevation=TEST_LOW_ELEVATION,  # Low sun elevation
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Direct azimuth
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                MOCK_COVER_ENTITY_ID_2: mock_cover_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        # Execute
        await sun_coordinator.async_refresh()
        result = sun_coordinator.data

        # Verify - Low sun elevation means sun_hitting = False, so covers should open
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN

    async def test_sun_automation_not_hitting_window_above_threshold(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test sun automation when sun is above threshold but not hitting window.

        Validates that when the sun is high enough but at an azimuth that doesn't
        align with the window orientation, the sun automation doesn't trigger closure.
        This ensures covers only close when the sun actually hits the configured window.

        Test scenario:
        - Sun elevation: 45° (above 20° threshold)
        - Sun azimuth: 90° (east) vs window facing 180° (south)
        - Temperature: 18°C (cold, supports opening)
        - Expected action: Open covers (sun not hitting window)
        """
        config = create_sun_config()
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Sun above threshold but azimuth far from south direction (window south)
        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_INDIRECT_AZIMUTH,  # 90° vs south 180° => angle 90° > tolerance
        }

        # Cover is partially closed to force potential change to OPEN
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_PARTIAL_POSITION

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={MOCK_COVER_ENTITY_ID: mock_cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_OPEN
        # Azimuth difference should be computed when elevation >= threshold
        assert cover_data[COVER_ATTR_SUN_AZIMUTH_DIFF] is not None

    async def test_sun_automation_no_sun_entity(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test critical error handling when sun entity is not found in Home Assistant.

        Validates that the coordinator treats missing sun entity as a critical error
        that makes the automation non-functional. Since sun position is essential for
        automation decisions, missing sun entity should make entities unavailable.

        Test scenario:
        - Sun entity: Missing from Home Assistant state registry
        - Expected behavior: Critical error logged, UpdateFailed exception raised, entities unavailable
        """
        # Create state mapping WITHOUT sun entity (to simulate missing sensor)
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        state_mapping = {
            MOCK_COVER_ENTITY_ID: cover_state,
            MOCK_TEMP_SENSOR_ENTITY_ID: MagicMock(entity_id=MOCK_TEMP_SENSOR_ENTITY_ID, state=TEST_COMFORTABLE_TEMP_1),
            # MOCK_SUN_ENTITY_ID is intentionally missing
        }

        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)
        await sun_coordinator.async_refresh()

        # Verify critical error handling - sun sensor missing
        assert isinstance(sun_coordinator.last_exception, UpdateFailed)  # Critical error should propagate
        assert "Sun sensor 'sun.sun' not found" in str(sun_coordinator.last_exception)

    async def test_sun_automation_invalid_data(
        self,
        sun_coordinator: DataUpdateCoordinator,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test critical error handling when sun entity provides invalid data.

        Validates that the coordinator treats invalid sun sensor readings as critical errors
        that make the automation non-functional. Since accurate sun position is essential for
        automation decisions, invalid sun data should make entities unavailable.

        Test scenario:
        - Sun entity: Returns "invalid" string for elevation
        - Expected behavior: Critical error logged, UpdateFailed exception raised, entities unavailable
        """
        mock_sun_state.attributes = {"elevation": "invalid", "azimuth": TEST_DIRECT_AZIMUTH}
        mock_hass.states.get.return_value = mock_sun_state
        await sun_coordinator.async_refresh()

        # Verify critical error handling
        assert isinstance(sun_coordinator.last_exception, UpdateFailed)  # Critical error should propagate
        assert "Invalid reading" in str(sun_coordinator.last_exception)

    async def test_sun_automation_skips_unavailable_cover(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that unavailable covers are skipped during sun automation.

        Validates that when one of multiple configured covers is unavailable,
        the automation continues processing available covers without errors.

        Test scenario:
        - Two covers configured
        - Second cover unavailable (not in state registry)
        - Expected behavior: First cover processed, second cover skipped
        """
        # Two covers configured; make second unavailable in the states mapping
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2])
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_DIRECT_AZIMUTH,
        }
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                # MOCK_COVER_ENTITY_ID_2 intentionally omitted to make it unavailable
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        # Only first cover should appear
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        assert MOCK_COVER_ENTITY_ID_2 not in result[ConfKeys.COVERS.value]

    async def test_sun_missing_cover_azimuth_skips_cover(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that covers without azimuth configuration are skipped in sun automation.

        Validates that covers missing window orientation configuration are excluded
        from sun automation but can still participate in temperature automation.

        Test scenario:
        - Two covers configured
        - Second cover missing azimuth/direction configuration
        - Expected behavior: Second cover skipped from sun automation
        """
        # Build a sun config for two covers, remove direction for second cover
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2])
        # Remove direction for cover 2 to trigger skip
        config.pop(f"{MOCK_COVER_ENTITY_ID_2}_{COVER_SFX_AZIMUTH}", None)
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Sun above threshold, direct hit
        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_DIRECT_AZIMUTH,
        }

        # Both covers available
        cover2_state = MagicMock()
        cover2_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                MOCK_COVER_ENTITY_ID_2: cover2_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Only cover 1 should appear (cover 2 is skipped due to missing azimuth)
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        assert MOCK_COVER_ENTITY_ID_2 not in result[ConfKeys.COVERS.value]

        # Cover 1 should have both temperature and sun automation data
        cover1_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result[SENSOR_ATTR_TEMP_HOT] is not None
        assert COVER_ATTR_SUN_HITTING in cover1_data

    async def test_sun_invalid_cover_azimuth_skips_cover(
        self,
        mock_hass: MagicMock,
        mock_cover_state: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that covers with invalid azimuth configuration are skipped.

        Validates that covers with invalid direction strings (non-numeric, non-cardinal)
        are excluded from sun automation with proper error handling.

        Test scenario:
        - Two covers configured
        - Second cover has invalid azimuth ("upwards")
        - Expected behavior: Second cover skipped from sun automation
        """
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2])
        # Set an invalid direction string for cover 2
        config[f"{MOCK_COVER_ENTITY_ID_2}_{COVER_SFX_AZIMUTH}"] = "upwards"
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": TEST_DIRECT_AZIMUTH,
        }

        cover2_state = MagicMock()
        cover2_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        mock_cover_state.attributes[ATTR_CURRENT_POSITION] = TEST_COVER_OPEN

        state_mapping = create_combined_state_mock(
            temp_state=TEST_COLD_TEMP,  # Cold temp so temp wants open
            cover_states={
                MOCK_COVER_ENTITY_ID: mock_cover_state.attributes,
                MOCK_COVER_ENTITY_ID_2: cover2_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data

        # Only cover 1 should appear (cover 2 is skipped due to invalid azimuth)
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        assert MOCK_COVER_ENTITY_ID_2 not in result[ConfKeys.COVERS.value]

        # Cover 1 should have both temperature and sun automation data
        cover1_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert result[SENSOR_ATTR_TEMP_HOT] is not None
        assert COVER_ATTR_SUN_HITTING in cover1_data

    @pytest.mark.asyncio
    async def test_sun_automation_angle_matrix(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test broad combinations of window and sun azimuths with combined logic.

        Validates automation behavior across various window orientations and sun positions
        to ensure the angle calculation and threshold logic work correctly in all scenarios.

        Test matrix includes:
        - Direct hits and misses
        - Edge cases near threshold boundaries
        - Wraparound scenarios (0°/360° boundary)
        """
        # Build config with one cover and numeric window azimuth
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        # Cover supports position and starts fully open
        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        for window_azimuth, sun_azimuth, expected in [
            (TEST_DIRECT_AZIMUTH, TEST_DIRECT_AZIMUTH, TEST_COVER_CLOSED),
            (TEST_DIRECT_AZIMUTH, 100.0, TEST_COVER_CLOSED),
            (TEST_DIRECT_AZIMUTH, 270.0, TEST_COVER_OPEN),
            (0.0, 350.0, TEST_COVER_CLOSED),
            (TEST_INDIRECT_AZIMUTH, 270.0, TEST_COVER_OPEN),
            (315.0, 44.0, TEST_COVER_CLOSED),
            (315.0, TEST_HIGH_ELEVATION, TEST_COVER_OPEN),
        ]:
            # Set numeric angle for window
            config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = window_azimuth

            # Sun above threshold with varying azimuth
            mock_sun_state.attributes = {
                "elevation": TEST_HIGH_ELEVATION,
                "azimuth": sun_azimuth,
            }

            # For combined logic: use hot temp when expecting close, cold temp when expecting open
            temp_for_test = TEST_HOT_TEMP if expected == TEST_COVER_CLOSED else TEST_COLD_TEMP

            mock_hass.services.async_call.reset_mock()
            state_mapping = create_combined_state_mock(
                temp_state=temp_for_test,
                sun_azimuth=sun_azimuth,
                cover_states={MOCK_COVER_ENTITY_ID: cover_state.attributes},
            )
            mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

            await coordinator.async_refresh()
            cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
            assert cover_data["sca_cover_desired_position"] == expected

    @pytest.mark.asyncio
    async def test_sun_automation_numeric_string_direction(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that numeric string directions are properly parsed as azimuths.

        Validates that window direction configuration accepts numeric strings
        (e.g., "180") and correctly parses them as azimuth degrees.

        Test scenario:
        - Window direction: "180" (string)
        - Sun azimuth: 180° (numeric)
        - Expected behavior: Direct hit recognition and proper closure
        """
        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = "180"
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        # Sun directly hitting numeric string direction
        mock_sun_state.attributes = {
            "elevation": TEST_HIGH_ELEVATION,
            "azimuth": 180.0,  # Matches "180" string direction
        }

        state_mapping = create_combined_state_mock(
            temp_state=TEST_HOT_TEMP,  # Hot temp supports closure
            sun_azimuth=180.0,
            cover_states={MOCK_COVER_ENTITY_ID: cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        result = coordinator.data
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        # Direct hit with hot temp should close covers
        assert cover_data["sca_cover_desired_position"] == TEST_COVER_CLOSED
