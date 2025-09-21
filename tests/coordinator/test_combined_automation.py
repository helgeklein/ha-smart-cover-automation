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
    COVER_POS_FULLY_OPEN,
    COVER_SFX_AZIMUTH,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_COVER_ENTITY_ID_2,
    MOCK_TEMP_SENSOR_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COMFORTABLE_TEMP_2,
    TEST_COVER_CLOSED,
    TEST_COVER_OPEN,
    TEST_DIRECT_AZIMUTH,
    TEST_HIGH_ELEVATION,
    TEST_HOT_TEMP,
    TEST_INDIRECT_AZIMUTH,
    MockConfigEntry,
    assert_service_called,
    create_combined_state_mock,
    create_sun_config,
    set_weather_forecast_temp,
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestCombinedAutomation(TestDataUpdateCoordinatorBase):
    """Test suite for combined temperature and sun automation logic."""

    @pytest.mark.asyncio
    async def test_sun_automation_multiple_covers_varied_angles(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test that only covers within tolerance close when sun hits.

        Validates that when multiple covers have different orientations, only those
        within the azimuth tolerance threshold actually close when the sun is positioned
        to hit them directly. This ensures precise control over which covers respond
        to sun conditions.

        Test scenario:
        - Cover 1: Facing 180° (south) - direct hit
        - Cover 2: Facing 90° (east) - indirect hit
        - Sun azimuth: 180° (south)
        - Expected: Cover 1 closes, Cover 2 opens
        """
        # Set weather forecast temperature to hot for this test
        set_weather_forecast_temp(float(TEST_HOT_TEMP))

        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2])
        config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = TEST_DIRECT_AZIMUTH
        config[f"{MOCK_COVER_ENTITY_ID_2}_{COVER_SFX_AZIMUTH}"] = TEST_INDIRECT_AZIMUTH
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        cover1_state = MagicMock()
        cover1_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        cover2_state = MagicMock()
        cover2_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }

        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}
        state_mapping = create_combined_state_mock(
            sun_azimuth=TEST_DIRECT_AZIMUTH,  # Sun hitting test_cover directly
            cover_states={
                MOCK_COVER_ENTITY_ID: cover1_state.attributes,
                MOCK_COVER_ENTITY_ID_2: cover2_state.attributes,
            },
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        covers = coordinator.data[ConfKeys.COVERS.value]
        assert covers[MOCK_COVER_ENTITY_ID]["sca_cover_desired_position"] == TEST_COVER_CLOSED
        assert covers[MOCK_COVER_ENTITY_ID_2]["sca_cover_desired_position"] == TEST_COVER_OPEN

        # Service called once for the closing cover
        await assert_service_called(
            mock_hass.services,
            "cover",
            "set_cover_position",
            MOCK_COVER_ENTITY_ID,
            position=TEST_COVER_CLOSED,
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

    @pytest.mark.asyncio
    async def test_sun_automation_max_closure_with_numeric_angle(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
    ) -> None:
        """Test partial closure with maximum closure percentage configuration.

        Validates that when the covers_max_closure setting is less than 100%,
        the automation respects this limit and only partially closes covers
        even during direct sun hits, maintaining some visibility and light.

        Test scenario:
        - Maximum closure: 60% (desired position = 40)
        - Sun: Direct hit at high elevation
        - Temperature: Cold (favors opening)
        - Expected: Combined logic results in open position
        """
        # Set weather forecast temperature to cold for this test
        set_weather_forecast_temp(float(TEST_COLD_TEMP))

        config = create_sun_config(covers=[MOCK_COVER_ENTITY_ID])
        config[ConfKeys.COVERS_MAX_CLOSURE.value] = 60  # 60% close => desired position 40
        config[f"{MOCK_COVER_ENTITY_ID}_{COVER_SFX_AZIMUTH}"] = TEST_DIRECT_AZIMUTH
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        cover_state = MagicMock()
        cover_state.attributes = {
            ATTR_CURRENT_POSITION: TEST_COVER_OPEN,
            ATTR_SUPPORTED_FEATURES: CoverEntityFeature.SET_POSITION,
        }
        mock_sun_state.attributes = {"elevation": TEST_HIGH_ELEVATION, "azimuth": TEST_DIRECT_AZIMUTH}

        state_mapping = create_combined_state_mock(
            cover_states={MOCK_COVER_ENTITY_ID: cover_state.attributes},
        )
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert cover_data["sca_cover_desired_position"] == COVER_POS_FULLY_OPEN  # Combined logic: cold temp overrides sun closure

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
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_TEMP_SENSOR_ENTITY_ID,
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
            ConfKeys.COVERS_MAX_CLOSURE.value: 60,  # partial closure => desired 40
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_TEMP_SENSOR_ENTITY_ID,
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
        # AND semantics: no action when temperature is not hot - verify no cover service calls
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
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_TEMP_SENSOR_ENTITY_ID,
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
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_TEMP_SENSOR_ENTITY_ID,
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
