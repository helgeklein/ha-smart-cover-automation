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
from homeassistant.const import ATTR_SUPPORTED_FEATURES

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.const import (
    COVER_ATTR_POS_TARGET_DESIRED,
    COVER_SFX_AZIMUTH,
    HA_WEATHER_COND_PARTCLOUDY,
    HA_WEATHER_COND_SUNNY,
)
from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_WEATHER_ENTITY_ID,
    TEST_COLD_TEMP,
    TEST_COMFORTABLE_TEMP_2,
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
        "sun_azimuth,max_closure,min_closure,forecast_temp,weather_condition,expected_position,test_description",
        [
            # Hot weather scenarios - Direct sun hitting window
            (TEST_DIRECT_AZIMUTH, 0, 100, TEST_HOT_TEMP, HA_WEATHER_COND_SUNNY, 0, "Hot sunny day, direct sun, full closure"),
            (TEST_DIRECT_AZIMUTH, 20, 100, TEST_HOT_TEMP, HA_WEATHER_COND_SUNNY, 20, "Hot sunny day, direct sun, limited max closure"),
            (TEST_DIRECT_AZIMUTH, 50, 100, TEST_HOT_TEMP, HA_WEATHER_COND_SUNNY, 50, "Hot sunny day, direct sun, moderate max closure"),
            (TEST_DIRECT_AZIMUTH, 0, 80, TEST_HOT_TEMP, HA_WEATHER_COND_PARTCLOUDY, 0, "Hot partly cloudy, direct sun, full closure"),
            (
                TEST_DIRECT_AZIMUTH,
                30,
                70,
                TEST_HOT_TEMP,
                HA_WEATHER_COND_PARTCLOUDY,
                30,
                "Hot partly cloudy, direct sun, max closure within min range",
            ),
            # Hot weather scenarios - Indirect sun (not hitting window)
            (TEST_INDIRECT_AZIMUTH, 0, 100, TEST_HOT_TEMP, HA_WEATHER_COND_SUNNY, 100, "Hot sunny day, indirect sun, full opening"),
            (
                TEST_INDIRECT_AZIMUTH,
                20,
                100,
                TEST_HOT_TEMP,
                HA_WEATHER_COND_SUNNY,
                100,
                "Hot sunny day, indirect sun, max closure irrelevant",
            ),
            (
                TEST_INDIRECT_AZIMUTH,
                50,
                80,
                TEST_HOT_TEMP,
                HA_WEATHER_COND_PARTCLOUDY,
                80,
                "Hot partly cloudy, indirect sun, min closure enforced",
            ),
            # Comfortable weather scenarios - Direct sun hitting window (temp < threshold, no temp automation)
            (
                TEST_DIRECT_AZIMUTH,
                0,
                100,
                TEST_COMFORTABLE_TEMP_2,
                HA_WEATHER_COND_SUNNY,
                100,
                "Comfortable sunny day, direct sun, temp below threshold",
            ),
            (
                TEST_DIRECT_AZIMUTH,
                40,
                100,
                TEST_COMFORTABLE_TEMP_2,
                HA_WEATHER_COND_SUNNY,
                100,
                "Comfortable sunny day, direct sun, temp below threshold",
            ),
            (
                TEST_DIRECT_AZIMUTH,
                0,
                60,
                TEST_COMFORTABLE_TEMP_2,
                HA_WEATHER_COND_PARTCLOUDY,
                60,
                "Comfortable partly cloudy, direct sun, min closure enforced",
            ),
            # Comfortable weather scenarios - Indirect sun (not hitting window)
            (
                TEST_INDIRECT_AZIMUTH,
                0,
                100,
                TEST_COMFORTABLE_TEMP_2,
                HA_WEATHER_COND_SUNNY,
                100,
                "Comfortable sunny day, indirect sun, full opening",
            ),
            (
                TEST_INDIRECT_AZIMUTH,
                30,
                70,
                TEST_COMFORTABLE_TEMP_2,
                HA_WEATHER_COND_SUNNY,
                70,
                "Comfortable sunny day, indirect sun, min closure enforced",
            ),
            (
                TEST_INDIRECT_AZIMUTH,
                0,
                50,
                TEST_COMFORTABLE_TEMP_2,
                HA_WEATHER_COND_PARTCLOUDY,
                50,
                "Comfortable partly cloudy, indirect sun, min closure limits",
            ),
            # Cold weather scenarios - Direct sun hitting window (temp < threshold, no temp automation)
            (TEST_DIRECT_AZIMUTH, 0, 100, TEST_COLD_TEMP, HA_WEATHER_COND_SUNNY, 100, "Cold sunny day, direct sun, temp below threshold"),
            (TEST_DIRECT_AZIMUTH, 60, 100, TEST_COLD_TEMP, HA_WEATHER_COND_SUNNY, 100, "Cold sunny day, direct sun, temp below threshold"),
            (
                TEST_DIRECT_AZIMUTH,
                30,
                80,
                TEST_COLD_TEMP,
                HA_WEATHER_COND_PARTCLOUDY,
                80,
                "Cold partly cloudy, direct sun, min closure enforced",
            ),
            # Cold weather scenarios - Indirect sun (not hitting window)
            (TEST_INDIRECT_AZIMUTH, 0, 100, TEST_COLD_TEMP, HA_WEATHER_COND_SUNNY, 100, "Cold sunny day, indirect sun, full opening"),
            (
                TEST_INDIRECT_AZIMUTH,
                20,
                80,
                TEST_COLD_TEMP,
                HA_WEATHER_COND_SUNNY,
                80,
                "Cold sunny day, indirect sun, min closure enforced",
            ),
            (
                TEST_INDIRECT_AZIMUTH,
                40,
                60,
                TEST_COLD_TEMP,
                HA_WEATHER_COND_PARTCLOUDY,
                60,
                "Cold partly cloudy, indirect sun, min closure limits opening",
            ),
            # Edge cases with different weather-temperature combinations
            (TEST_DIRECT_AZIMUTH, 10, 90, TEST_HOT_TEMP, HA_WEATHER_COND_SUNNY, 10, "Hot sunny edge case, tight max closure"),
            (
                TEST_INDIRECT_AZIMUTH,
                25,
                35,
                TEST_COLD_TEMP,
                HA_WEATHER_COND_PARTCLOUDY,
                35,
                "Cold partly cloudy edge case, min closure tighter than max",
            ),
            # Non-sunny weather scenarios - Covers should remain open regardless of temperature/sun
            (TEST_DIRECT_AZIMUTH, 0, 100, TEST_HOT_TEMP, "cloudy", 100, "Hot cloudy day, direct sun, covers stay open"),
            (TEST_DIRECT_AZIMUTH, 20, 100, TEST_HOT_TEMP, "rainy", 100, "Hot rainy day, direct sun, covers stay open"),
            (TEST_DIRECT_AZIMUTH, 50, 100, TEST_HOT_TEMP, "foggy", 100, "Hot foggy day, direct sun, covers stay open"),
            (TEST_DIRECT_AZIMUTH, 0, 80, TEST_COMFORTABLE_TEMP_2, "cloudy", 80, "Comfortable cloudy day, min closure enforced"),
            (TEST_DIRECT_AZIMUTH, 30, 70, TEST_COLD_TEMP, "rainy", 70, "Cold rainy day, min closure enforced"),
            (TEST_INDIRECT_AZIMUTH, 0, 100, TEST_HOT_TEMP, "snowy", 100, "Hot snowy day, indirect sun, covers stay open"),
            (TEST_INDIRECT_AZIMUTH, 40, 60, TEST_COMFORTABLE_TEMP_2, "foggy", 60, "Comfortable foggy day, min closure enforced"),
            (TEST_INDIRECT_AZIMUTH, 0, 50, TEST_COLD_TEMP, "cloudy", 50, "Cold cloudy day, min closure enforced"),
            # Non-sunny weather with extreme temperatures - Still no sun automation
            (TEST_DIRECT_AZIMUTH, 0, 100, "30.0", "stormy", 100, "Extremely hot stormy day, covers stay open"),
            (TEST_DIRECT_AZIMUTH, 20, 100, "15.0", "hail", 100, "Very cold hail day, covers stay open"),
        ],
    )
    async def test_sun_automation_closure_position_matrix(
        self,
        mock_hass: MagicMock,
        mock_sun_state: MagicMock,
        sun_azimuth: float,
        max_closure: int,
        min_closure: int,
        forecast_temp: str,
        weather_condition: str,
        expected_position: int,
        test_description: str,
    ) -> None:
        """Test comprehensive closure position matrix with weather conditions and temperatures.

        Validates that the automation correctly applies min/max closure limits based on
        sun position, weather forecast temperature, and weather conditions. The combined
        automation considers both sun direction and weather conditions to determine
        optimal cover positions.

        Test matrix covers:
        - Hot weather scenarios (sunny/partly cloudy) with direct/indirect sun
        - Comfortable weather scenarios with various sun positions
        - Cold weather scenarios where sun warmth is desired
        - Non-sunny weather scenarios (cloudy, rainy, foggy, etc.) where covers stay open
        - Direct sun hits with various max_closure limits
        - Indirect sun with various min_closure limits
        - Edge cases where min/max ranges overlap
        - Multiple weather condition combinations
        - Temperature-driven automation behaviors
        - Weather condition override scenarios (non-sunny conditions disable sun automation)
        """
        # Set weather forecast temperature for this test case
        set_weather_forecast_temp(float(forecast_temp))

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
        # Set the weather condition for this test case
        state_mapping[MOCK_WEATHER_ENTITY_ID].state = weather_condition
        mock_hass.states.get.side_effect = lambda entity_id: state_mapping.get(entity_id)

        await coordinator.async_refresh()
        cover_data = coordinator.data[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]

        assert cover_data[COVER_ATTR_POS_TARGET_DESIRED] == expected_position, (
            f"Test case: {test_description}\n"
            f"Sun azimuth: {sun_azimuth}°, Temperature: {forecast_temp}°C, Weather: {weather_condition}\n"
            f"Max closure: {max_closure}%, Min closure: {min_closure}%\n"
            f"Expected position: {expected_position}%, Got: {cover_data[COVER_ATTR_POS_TARGET_DESIRED]}%"
        )

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

        # Cover should be present with error due to missing direction
        assert MOCK_COVER_ENTITY_ID in result[ConfKeys.COVERS.value]
        cover_data = result[ConfKeys.COVERS.value][MOCK_COVER_ENTITY_ID]
        assert "sca_cover_error" in cover_data
        assert "invalid or missing azimuth" in cover_data["sca_cover_error"]
