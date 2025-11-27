"""End-to-end scenario tests for the options flow.

These tests verify complete user workflows through the entire options flow,
simulating realistic interaction patterns such as:
- Clicking through all steps without making changes
- Adding new per-cover settings
- Clearing existing per-cover settings
- Adding window sensors for lockout protection
- Removing covers and verifying cleanup

These tests complement the granular unit tests in test_options_flow.py
by focusing on complete user journeys.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.data_entry_flow import FlowResultType

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler
from custom_components.smart_cover_automation.const import (
    COVER_SFX_AZIMUTH,
    COVER_SFX_MAX_CLOSURE,
    COVER_SFX_MIN_CLOSURE,
    COVER_SFX_WINDOW_SENSORS,
    STEP_3_SECTION_MAX_CLOSURE,
    STEP_3_SECTION_MIN_CLOSURE,
    STEP_4_SECTION_WINDOW_SENSORS,
)

# Test constants
TEST_COVER_1 = "cover.living_room"
TEST_COVER_2 = "cover.bedroom"
TEST_WEATHER = "weather.home"
TEST_BINARY_SENSOR = "binary_sensor.window_sensor"


def _as_dict(result: ConfigFlowResult) -> dict[str, Any]:
    """Convert ConfigFlowResult to dictionary for test assertions."""
    return cast(dict[str, Any], result)


#
# _create_mock_config_entry
#
def _create_mock_config_entry(options: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock config entry for testing.

    Args:
        options: Initial options for the config entry

    Returns:
        Mock config entry object
    """

    entry = MagicMock()
    entry.options = options or {}
    return entry


class TestOptionsFlowScenarios:
    """Test complete user workflow scenarios through options flow."""

    #
    # test_complete_options_flow_no_changes
    #
    async def test_complete_options_flow_no_changes(self) -> None:
        """Test clicking through entire options flow without making changes.

        This simulates a user opening the options flow, clicking through all
        steps without modifying any values, and verifying no spurious "new
        settings" are logged.
        """

        # Create initial config entry with existing settings
        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}": 20,  # Existing per-cover setting
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Step init - user clicks "Next"
        result = await flow.async_step_init(None)
        result_dict = _as_dict(result)
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "init"

        # Step 2 - azimuth per cover (no change)
        user_input = {
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
        }
        result = await flow.async_step_2(user_input)
        result_dict = _as_dict(result)
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "3"

        # Step 3 - min/max closure per cover (no change - section auto-populated)
        # Simulate HA UI auto-populating ALL covers with None/default values
        user_input = {
            STEP_3_SECTION_MIN_CLOSURE: {
                f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}": None,  # Auto-populated default
                f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}": None,  # Auto-populated default
            },
            STEP_3_SECTION_MAX_CLOSURE: {
                f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}": 20,  # Existing value unchanged
                f"{TEST_COVER_2}_{COVER_SFX_MAX_CLOSURE}": None,  # Auto-populated default
            },
        }
        result = await flow.async_step_3(user_input)
        result_dict = _as_dict(result)
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "4"

        # Step 4 - window sensors (no change - section auto-populated)
        # Simulate HA UI auto-populating ALL covers with empty lists
        user_input = {
            STEP_4_SECTION_WINDOW_SENSORS: {
                f"{TEST_COVER_1}_{COVER_SFX_WINDOW_SENSORS}": [],  # Auto-populated default
                f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}": [],  # Auto-populated default
            },
        }
        result = await flow.async_step_4(user_input)
        result_dict = _as_dict(result)
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "5"

        # Step 5 - global settings (no change)
        user_input = {
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }
        result = await flow.async_step_5(user_input)
        result_dict = _as_dict(result)

        # Verify flow completes successfully
        assert result_dict["type"] == FlowResultType.CREATE_ENTRY

        # Verify options unchanged (no false "new settings")
        final_options = result_dict["data"]
        assert final_options == initial_options

    #
    # test_options_flow_add_per_cover_setting
    #
    async def test_options_flow_add_per_cover_setting(self) -> None:
        """Test adding a new per-cover min closure setting.

        This simulates a user adding a custom min closure value for one cover
        while leaving other covers at global defaults.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-2 unchanged
        await flow.async_step_init(None)
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            }
        )

        # Step 3 - Add min closure for TEST_COVER_1 only
        user_input = {
            STEP_3_SECTION_MIN_CLOSURE: {
                f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}": 30,  # New setting
            },
            STEP_3_SECTION_MAX_CLOSURE: {},  # No changes
        }
        await flow.async_step_3(user_input)

        # Step 4 - No changes to window sensors
        await flow.async_step_4({STEP_4_SECTION_WINDOW_SENSORS: {}})

        # Step 5 - Complete flow
        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify new setting added
        assert f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}" in final_options
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}"] == 30

        # Verify TEST_COVER_2 has no per-cover setting (uses global)
        assert f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}" not in final_options

    #
    # test_options_flow_clear_per_cover_setting
    #
    async def test_options_flow_clear_per_cover_setting(self) -> None:
        """Test clearing an existing per-cover max closure setting.

        This simulates a user removing a custom max closure value to revert
        to the global default.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}": 20,  # Existing setting to be cleared
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-2 unchanged
        await flow.async_step_init(None)
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            }
        )

        # Step 3 - Clear max closure for TEST_COVER_1
        # User clears the field, HA sends None
        user_input = {
            STEP_3_SECTION_MIN_CLOSURE: {},
            STEP_3_SECTION_MAX_CLOSURE: {
                f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}": None,  # Explicit clear
            },
        }
        await flow.async_step_3(user_input)

        # Step 4 - No changes to window sensors
        await flow.async_step_4({STEP_4_SECTION_WINDOW_SENSORS: {}})

        # Step 5 - Complete flow
        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify setting was cleared
        assert f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}" not in final_options

    #
    # test_options_flow_add_window_sensor
    #
    async def test_options_flow_add_window_sensor(self) -> None:
        """Test adding a window sensor for lockout protection.

        This simulates a user adding a window sensor to prevent automation
        when the window is open.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-3 unchanged
        await flow.async_step_init(None)
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            }
        )
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {},
                STEP_3_SECTION_MAX_CLOSURE: {},
            }
        )

        # Step 4 - Add window sensor for TEST_COVER_1
        user_input = {
            STEP_4_SECTION_WINDOW_SENSORS: {
                f"{TEST_COVER_1}_{COVER_SFX_WINDOW_SENSORS}": [TEST_BINARY_SENSOR],  # New sensor
            },
        }
        await flow.async_step_4(user_input)

        # Step 5 - Complete flow
        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify window sensor added
        assert f"{TEST_COVER_1}_{COVER_SFX_WINDOW_SENSORS}" in final_options
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_WINDOW_SENSORS}"] == [TEST_BINARY_SENSOR]

        # Verify TEST_COVER_2 has no window sensors
        assert f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}" not in final_options

    #
    # test_options_flow_remove_cover
    #
    async def test_options_flow_remove_cover(self) -> None:
        """Test removing a cover and verifying all related settings are cleaned up.

        This simulates a user removing a cover from the configuration and
        ensures all per-cover settings are properly removed.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}": 30,  # Per-cover setting for TEST_COVER_2
            f"{TEST_COVER_2}_{COVER_SFX_MAX_CLOSURE}": 70,  # Per-cover setting for TEST_COVER_2
            f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}": [TEST_BINARY_SENSOR],  # Window sensor
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-2, removing TEST_COVER_2
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
                ConfKeys.COVERS.value: [TEST_COVER_1],  # Only TEST_COVER_1 remains
            }
        )
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            }
        )

        # Continue through remaining steps
        # Step 3 - min/max settings
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {},
                STEP_3_SECTION_MAX_CLOSURE: {},
            }
        )
        # Step 4 - window sensors
        await flow.async_step_4({STEP_4_SECTION_WINDOW_SENSORS: {}})

        # Step 5 - Complete flow
        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify TEST_COVER_2 and all its settings were removed
        assert TEST_COVER_2 not in final_options[ConfKeys.COVERS.value]
        assert f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}" not in final_options
        assert f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}" not in final_options
        assert f"{TEST_COVER_2}_{COVER_SFX_MAX_CLOSURE}" not in final_options
        assert f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}" not in final_options

        # Verify TEST_COVER_1 remains
        assert TEST_COVER_1 in final_options[ConfKeys.COVERS.value]
        assert f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}" in final_options

    #
    # test_options_flow_modify_multiple_per_cover_settings
    #
    async def test_options_flow_modify_multiple_per_cover_settings(self) -> None:
        """Test modifying multiple per-cover settings simultaneously.

        This simulates a user configuring multiple covers with different
        min/max closures and window sensors in a single configuration session.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-2
        await flow.async_step_init(None)
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            }
        )

        # Step 3 - Add both min and max closures for both covers
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {
                    f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}": 10,
                    f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}": 20,
                },
                STEP_3_SECTION_MAX_CLOSURE: {
                    f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}": 80,
                    f"{TEST_COVER_2}_{COVER_SFX_MAX_CLOSURE}": 90,
                },
            }
        )

        # Step 4 - Add window sensors for both covers
        await flow.async_step_4(
            {
                STEP_4_SECTION_WINDOW_SENSORS: {
                    f"{TEST_COVER_1}_{COVER_SFX_WINDOW_SENSORS}": [TEST_BINARY_SENSOR],
                    f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}": ["binary_sensor.window_2"],
                },
            }
        )

        # Step 5 - Complete flow
        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify all settings for TEST_COVER_1
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}"] == 10
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}"] == 80
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_WINDOW_SENSORS}"] == [TEST_BINARY_SENSOR]

        # Verify all settings for TEST_COVER_2
        assert final_options[f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}"] == 20
        assert final_options[f"{TEST_COVER_2}_{COVER_SFX_MAX_CLOSURE}"] == 90
        assert final_options[f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}"] == ["binary_sensor.window_2"]

    #
    # test_options_flow_change_weather_entity
    #
    async def test_options_flow_change_weather_entity(self) -> None:
        """Test changing the weather entity.

        This simulates a user switching to a different weather entity,
        which might happen when changing weather providers.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Step init - Change weather entity
        new_weather = "weather.forecast_home"
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: new_weather,
                ConfKeys.COVERS.value: [TEST_COVER_1],
            }
        )

        # Step 2 - Azimuth unchanged
        await flow.async_step_2({f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0})

        # Continue through remaining steps
        # Step 3 - min/max settings
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {},
                STEP_3_SECTION_MAX_CLOSURE: {},
            }
        )
        # Step 4 - window sensors
        await flow.async_step_4({STEP_4_SECTION_WINDOW_SENSORS: {}})

        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify weather entity changed
        assert final_options[ConfKeys.WEATHER_ENTITY_ID.value] == new_weather

    #
    # test_options_flow_change_cover_azimuth
    #
    async def test_options_flow_change_cover_azimuth(self) -> None:
        """Test changing cover azimuth values.

        This simulates a user adjusting the azimuth (direction) values for
        covers, which might happen after physically repositioning them.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-2
        await flow.async_step_init(None)
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 270.0,  # Changed from 180
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 45.0,  # Changed from 90
            }
        )

        # Continue through remaining steps
        # Step 3 - min/max settings
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {},
                STEP_3_SECTION_MAX_CLOSURE: {},
            }
        )
        # Step 4 - window sensors
        await flow.async_step_4({STEP_4_SECTION_WINDOW_SENSORS: {}})

        # Step 5 - Complete flow
        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify azimuth values changed
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}"] == 270.0
        assert final_options[f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}"] == 45.0

    #
    # test_options_flow_change_global_settings
    #
    async def test_options_flow_change_global_settings(self) -> None:
        """Test changing global automation settings.

        This simulates a user adjusting thresholds, tolerances, and other
        global settings that apply to all covers.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-4
        await flow.async_step_init(None)
        await flow.async_step_2({f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0})
        # Step 3 - min/max settings
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {},
                STEP_3_SECTION_MAX_CLOSURE: {},
            }
        )
        # Step 4 - window sensors
        await flow.async_step_4({STEP_4_SECTION_WINDOW_SENSORS: {}})

        # Step 5 - Change global settings
        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 30.0,  # Changed
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 45.0,  # Changed
                ConfKeys.COVERS_MAX_CLOSURE.value: 75.0,  # Changed
                ConfKeys.COVERS_MIN_CLOSURE.value: 25.0,  # Changed
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 1, "minutes": 0, "seconds": 0},  # Changed
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: False,  # Changed
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify all global settings changed
        assert final_options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == 30.0
        assert final_options[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] == 45.0
        assert final_options[ConfKeys.COVERS_MAX_CLOSURE.value] == 75.0
        assert final_options[ConfKeys.COVERS_MIN_CLOSURE.value] == 25.0
        assert final_options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] == {"hours": 1, "minutes": 0, "seconds": 0}
        assert final_options[ConfKeys.NIGHTTIME_BLOCK_OPENING.value] is False

    #
    # test_options_flow_add_new_cover
    #
    async def test_options_flow_add_new_cover(self) -> None:
        """Test adding a new cover to the configuration.

        This simulates a user adding a new cover entity with its
        azimuth and optionally per-cover settings.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}": 10,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-2
        test_cover_3 = "cover.office"
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
                ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2, test_cover_3],  # Add two new covers
            }
        )
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
                f"{test_cover_3}_{COVER_SFX_AZIMUTH}": 270.0,
            }
        )

        # Step 3 - Add settings for new covers
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {
                    f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}": 10,  # Existing
                    f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}": 15,  # New
                },
                STEP_3_SECTION_MAX_CLOSURE: {},
            }
        )

        await flow.async_step_4({STEP_4_SECTION_WINDOW_SENSORS: {}})

        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify new covers added
        assert len(final_options[ConfKeys.COVERS.value]) == 3
        assert TEST_COVER_2 in final_options[ConfKeys.COVERS.value]
        assert test_cover_3 in final_options[ConfKeys.COVERS.value]

        # Verify azimuth for new covers
        assert final_options[f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}"] == 90.0
        assert final_options[f"{test_cover_3}_{COVER_SFX_AZIMUTH}"] == 270.0

        # Verify per-cover settings
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}"] == 10
        assert final_options[f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}"] == 15

    #
    # test_options_flow_remove_window_sensor
    #
    async def test_options_flow_remove_window_sensor(self) -> None:
        """Test removing window sensors from a cover.

        This simulates a user removing window sensor associations,
        perhaps because the sensor was removed or is no longer needed.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            f"{TEST_COVER_1}_{COVER_SFX_WINDOW_SENSORS}": [TEST_BINARY_SENSOR],
            f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}": ["binary_sensor.window_2"],
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-3
        await flow.async_step_init(None)
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            }
        )
        # Step 3 - min/max settings
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {},
                STEP_3_SECTION_MAX_CLOSURE: {},
            }
        )

        # Step 4 - Remove window sensors by setting to empty list
        await flow.async_step_4(
            {
                STEP_4_SECTION_WINDOW_SENSORS: {
                    f"{TEST_COVER_1}_{COVER_SFX_WINDOW_SENSORS}": [],  # Explicit removal
                    f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}": ["binary_sensor.window_2"],  # Keep
                },
            }
        )

        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify TEST_COVER_1 window sensors set to empty (explicitly removed)
        # Empty list means "no window sensors" which is a valid configuration
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_WINDOW_SENSORS}"] == []

        # Verify TEST_COVER_2 window sensors kept
        assert final_options[f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}"] == ["binary_sensor.window_2"]

    #
    # test_options_flow_update_existing_per_cover_settings
    #
    async def test_options_flow_update_existing_per_cover_settings(self) -> None:
        """Test updating existing per-cover min/max closure values.

        This simulates a user adjusting closure limits that were
        previously configured.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}": 10,
            f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}": 80,
            f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}": 20,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Navigate through steps 1-2
        await flow.async_step_init(None)
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
                f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            }
        )

        # Step 3 - Update existing values
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {
                    f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}": 30,  # Changed from 10
                    f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}": 20,  # Unchanged
                },
                STEP_3_SECTION_MAX_CLOSURE: {
                    f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}": 60,  # Changed from 80
                    f"{TEST_COVER_2}_{COVER_SFX_MAX_CLOSURE}": None,  # No max for cover 2
                },
            }
        )

        await flow.async_step_4({STEP_4_SECTION_WINDOW_SENSORS: {}})

        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify updated values
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}"] == 30
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}"] == 60
        assert final_options[f"{TEST_COVER_2}_{COVER_SFX_MIN_CLOSURE}"] == 20
        assert f"{TEST_COVER_2}_{COVER_SFX_MAX_CLOSURE}" not in final_options

    #
    # test_options_flow_mixed_changes
    #
    async def test_options_flow_mixed_changes(self) -> None:
        """Test a complex scenario with multiple types of changes.

        This simulates a realistic session where a user makes various
        changes: adds covers, removes covers, updates settings, changes
        global config, etc. all in one go.
        """

        initial_options = {
            ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
            ConfKeys.COVERS.value: [TEST_COVER_1, TEST_COVER_2],
            f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 180.0,
            f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}": 90.0,
            f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}": 10,
            f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}": [TEST_BINARY_SENSOR],
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20.0,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100.0,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0.0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.NIGHTTIME_BLOCK_OPENING.value: True,
        }

        entry = _create_mock_config_entry(options=initial_options)
        flow = OptionsFlowHandler(entry)

        # Step init - Remove TEST_COVER_2, add new cover
        test_cover_3 = "cover.kitchen"
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: TEST_WEATHER,
                ConfKeys.COVERS.value: [TEST_COVER_1, test_cover_3],  # Remove TEST_COVER_2, add test_cover_3
            }
        )

        # Step 2 - Set azimuth for covers, change TEST_COVER_1 azimuth
        await flow.async_step_2(
            {
                f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}": 200.0,  # Changed from 180
                f"{test_cover_3}_{COVER_SFX_AZIMUTH}": 135.0,  # New cover
            }
        )

        # Step 3 - Update min closure for cover 1, add settings for cover 3
        await flow.async_step_3(
            {
                STEP_3_SECTION_MIN_CLOSURE: {
                    f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}": 25,  # Changed from 10
                    f"{test_cover_3}_{COVER_SFX_MIN_CLOSURE}": 30,  # New
                },
                STEP_3_SECTION_MAX_CLOSURE: {
                    f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}": 70,  # New
                    f"{test_cover_3}_{COVER_SFX_MAX_CLOSURE}": None,  # No max
                },
            }
        )

        # Step 4 - Add window sensor for new cover
        await flow.async_step_4(
            {
                STEP_4_SECTION_WINDOW_SENSORS: {
                    f"{test_cover_3}_{COVER_SFX_WINDOW_SENSORS}": ["binary_sensor.kitchen_window"],
                },
            }
        )

        # Step 5 - Change some global settings
        result = await flow.async_step_5(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 25.0,  # Changed
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90.0,  # Unchanged
                ConfKeys.COVERS_MAX_CLOSURE.value: 90.0,  # Changed
                ConfKeys.COVERS_MIN_CLOSURE.value: 10.0,  # Changed
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 45, "seconds": 0},  # Changed
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value: False,  # Changed
            }
        )

        result_dict = _as_dict(result)
        final_options = result_dict["data"]

        # Verify cover changes
        assert len(final_options[ConfKeys.COVERS.value]) == 2
        assert TEST_COVER_1 in final_options[ConfKeys.COVERS.value]
        assert test_cover_3 in final_options[ConfKeys.COVERS.value]
        assert TEST_COVER_2 not in final_options[ConfKeys.COVERS.value]

        # Verify TEST_COVER_2 settings removed (cover was removed)
        assert f"{TEST_COVER_2}_{COVER_SFX_AZIMUTH}" not in final_options
        assert f"{TEST_COVER_2}_{COVER_SFX_WINDOW_SENSORS}" not in final_options

        # Verify TEST_COVER_1 changes
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_AZIMUTH}"] == 200.0
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_MIN_CLOSURE}"] == 25
        assert final_options[f"{TEST_COVER_1}_{COVER_SFX_MAX_CLOSURE}"] == 70

        # Verify new cover settings
        assert final_options[f"{test_cover_3}_{COVER_SFX_AZIMUTH}"] == 135.0
        assert final_options[f"{test_cover_3}_{COVER_SFX_MIN_CLOSURE}"] == 30
        assert f"{test_cover_3}_{COVER_SFX_MAX_CLOSURE}" not in final_options
        assert final_options[f"{test_cover_3}_{COVER_SFX_WINDOW_SENSORS}"] == ["binary_sensor.kitchen_window"]

        # Verify global settings changed
        assert final_options[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == 25.0
        assert final_options[ConfKeys.COVERS_MAX_CLOSURE.value] == 90.0
        assert final_options[ConfKeys.COVERS_MIN_CLOSURE.value] == 10.0
        assert final_options[ConfKeys.MANUAL_OVERRIDE_DURATION.value] == {"hours": 0, "minutes": 45, "seconds": 0}
        assert final_options[ConfKeys.NIGHTTIME_BLOCK_OPENING.value] is False
