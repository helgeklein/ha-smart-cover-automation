"""Tests for the Smart Cover Automation options flow.

This module tests the configuration options flow for modifying settings after
initial setup. The flow has 3 steps matching the config flow:
1. Cover and weather entity selection
2. Azimuth configuration per cover
3. Sun position, cover behavior, and manual override settings
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.data_entry_flow import FlowResultType

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

from ..conftest import MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2, MOCK_WEATHER_ENTITY_ID


def _as_dict(result: ConfigFlowResult) -> dict[str, Any]:
    """Convert ConfigFlowResult to dictionary for test assertions."""
    return cast(dict[str, Any], result)


def _create_mock_entry(data: dict[str, Any] | None = None, options: dict[str, Any] | None = None) -> MagicMock:
    """Create a mock config entry for testing.

    If data is provided and options is None, data is moved to options (since all
    user settings are now stored in options, not data).
    """
    mock_entry = MagicMock()
    # Config entry data is empty (only marks integration as installed)
    mock_entry.data = {}
    # All user settings are in options
    if options is not None:
        mock_entry.options = options
    elif data is not None:
        # Legacy test helper: if data is provided, put it in options
        mock_entry.options = data
    else:
        mock_entry.options = {}
    return mock_entry


class TestOptionsFlowStep1:
    """Test step 1 (init): Cover and weather entity selection."""

    async def test_step_init_shows_form_with_existing_config(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 1 shows form on initial entry."""
        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        result = await flow.async_step_init(None)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "init"

    async def test_step_init_validates_and_proceeds_to_step2(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that valid input proceeds to step 2."""
        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],  # Add a cover
        }

        result = await flow.async_step_init(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "2"
        assert ConfKeys.COVERS.value in flow._config_data
        assert MOCK_COVER_ENTITY_ID_2 in flow._config_data[ConfKeys.COVERS.value]

    async def test_step_init_error_no_covers(self, mock_hass_with_covers: MagicMock) -> None:
        """Test error when no covers are selected."""
        mock_entry = _create_mock_entry()
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [],
        }

        result = await flow.async_step_init(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "init"
        assert ConfKeys.COVERS.value in result_dict["errors"]
        assert result_dict["errors"][ConfKeys.COVERS.value] == const.ERROR_NO_COVERS

    async def test_step_init_options_override_data(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that options values override data values as defaults."""
        data = {
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.old",
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }
        options = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,  # Override
        }
        mock_entry = _create_mock_entry(data=data, options=options)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        result = await flow.async_step_init(None)
        result_dict = _as_dict(result)

        # Form should be shown on initial entry
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "init"


class TestOptionsFlowStep2:
    """Test step 2: Azimuth configuration per cover."""

    async def test_step_2_fallback_to_existing_config_when_no_accumulated_data(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 2 falls back to existing config when _config_data is empty."""
        existing_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers
        # Don't set flow._config_data - simulates jumping directly to step 2 from menu

        result = await flow.async_step_2(None)
        result_dict = _as_dict(result)

        # Should show form with covers from existing config
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "2"
        # The form should include azimuth fields for the cover from existing config

    async def test_step_2_shows_azimuth_fields_for_covers(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 2 shows azimuth fields for selected covers."""
        existing_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers
        flow._config_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        }

        result = await flow.async_step_2(None)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "2"

        schema = result_dict["data_schema"].schema
        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.keys()]

        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in schema_keys
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}" in schema_keys

    async def test_step_2_uses_existing_azimuth_as_default(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that existing azimuth values are used as defaults."""
        existing_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 135.0,
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers
        flow._config_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        result = await flow.async_step_2(None)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "2"

    async def test_step_2_proceeds_to_step3(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that valid azimuth input proceeds to step 3."""
        mock_entry = _create_mock_entry()
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers
        flow._config_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        user_input = {
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 225.0,
        }

        result = await flow.async_step_2(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "3"
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in flow._config_data


class TestOptionsFlowStep3:
    """Test step 3: Sun position, cover behavior, and manual override settings."""

    async def test_step_3_shows_all_settings(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 3 shows all final settings."""
        mock_entry = _create_mock_entry()
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers
        flow._config_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        result = await flow.async_step_3(None)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "3"

        schema = result_dict["data_schema"].schema
        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.keys()]

        # All numeric settings are now number entities, step 3 is empty
        assert len(schema_keys) == 0

    async def test_step_3_creates_entry_with_updated_config(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 3 proceeds to step 4."""
        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers
        flow._config_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
        }

        user_input = {
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 35,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 75,
            ConfKeys.COVERS_MAX_CLOSURE.value: 85,
            ConfKeys.COVERS_MIN_CLOSURE.value: 15,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 3, "minutes": 0, "seconds": 0},
        }

        result3 = await flow.async_step_3(user_input)
        result3_dict = _as_dict(result3)

        # Step 3 now proceeds to step 4
        assert result3_dict["type"] == FlowResultType.FORM
        assert result3_dict["step_id"] == "4"

    async def test_step_3_cleans_up_orphaned_cover_settings(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that orphaned cover settings are removed when covers change."""
        existing_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # User removed MOCK_COVER_ENTITY_ID_2 in step 1
        flow._config_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],  # Only one cover now
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,  # Should be removed
        }

        user_input = {
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 2, "minutes": 0, "seconds": 0},
        }

        result3 = await flow.async_step_3(user_input)
        result3_dict = _as_dict(result3)

        # Step 3 now proceeds to step 4
        assert result3_dict["type"] == FlowResultType.FORM
        assert result3_dict["step_id"] == "4"

        # Now complete step 4 to proceed to step 5
        result4 = await flow.async_step_4({})
        result4_dict = _as_dict(result4)
        assert result4_dict["type"] == FlowResultType.FORM
        assert result4_dict["step_id"] == "5"

        # Now complete step 5 to proceed to step 6
        result5 = await flow.async_step_5({})
        result5_dict = _as_dict(result5)
        assert result5_dict["type"] == FlowResultType.FORM
        assert result5_dict["step_id"] == "6"

        # Now complete step 6 to create entry
        result6 = await flow.async_step_6({})
        result6_dict = _as_dict(result6)
        assert result6_dict["type"] == FlowResultType.CREATE_ENTRY

        data = result6_dict["data"]
        # First cover's azimuth should remain
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in data
        # Second cover's azimuth should be removed
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}" not in data


class TestOptionsFlowIntegration:
    """Test complete options flow from start to finish."""

    async def test_complete_options_flow(self, mock_hass_with_covers: MagicMock) -> None:
        """Test complete 3-step options flow."""
        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Step 1: Update covers (submitting data goes directly to step 2 form)
        result1 = await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            }
        )
        assert _as_dict(result1)["type"] == FlowResultType.FORM
        assert _as_dict(result1)["step_id"] == "2"

        # Step 2: Configure azimuth for both covers (now proceeds directly to step 3)
        result2 = await flow.async_step_2(
            {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
                f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 270.0,
            }
        )
        assert _as_dict(result2)["type"] == FlowResultType.FORM
        assert _as_dict(result2)["step_id"] == "3"

        # Step 3: Submit data (now proceeds to step 4)
        result3 = await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 25,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 80,
                ConfKeys.COVERS_MAX_CLOSURE.value: 90,
                ConfKeys.COVERS_MIN_CLOSURE.value: 10,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 2, "minutes": 30, "seconds": 0},
            }
        )
        result3_dict = _as_dict(result3)
        assert result3_dict["type"] == FlowResultType.FORM
        assert result3_dict["step_id"] == "4"

        # Step 4: Submit per-cover settings (now proceeds to step 5)
        result4 = await flow.async_step_4({})
        result4_dict = _as_dict(result4)
        assert result4_dict["type"] == FlowResultType.FORM
        assert result4_dict["step_id"] == "5"

        # Step 5: Submit window sensors (now proceeds to step 6)
        result5 = await flow.async_step_5({})
        result5_dict = _as_dict(result5)
        assert result5_dict["type"] == FlowResultType.FORM
        assert result5_dict["step_id"] == "6"

        # Step 6: Submit night settings (creates entry)
        result6 = await flow.async_step_6({})
        result6_dict = _as_dict(result6)
        assert result6_dict["type"] == FlowResultType.CREATE_ENTRY

        # Verify updated configuration
        data = result6_dict["data"]
        assert len(data[ConfKeys.COVERS.value]) == 2
        assert data[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == 25
        assert data[f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}"] == 270.0

    async def test_removing_cover_removes_its_azimuth(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that removing a cover also removes its azimuth setting."""
        existing_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Step 1: Remove second cover
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],  # Removed MOCK_COVER_ENTITY_ID_2
            }
        )

        # Step 2: Configure remaining cover
        await flow.async_step_2(
            {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            }
        )

        # Step 3: Submit settings (proceeds to step 4)
        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 2, "minutes": 0, "seconds": 0},
            }
        )

        # Step 4: Continue (proceeds to step 5)
        await flow.async_step_4({})

        # Step 5: Continue (proceeds to step 6)
        await flow.async_step_5({})

        # Step 6: Complete (creates entry)
        result = await flow.async_step_6({})

        data = _as_dict(result)["data"]
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in data
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}" not in data

    async def test_preserves_settings_not_in_ui(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that settings not in the UI (like simulation_mode) are preserved.

        This is a regression test for the bug where submitting the options flow
        would reset simulation_mode, enabled, verbose_logging, and other settings
        that are controlled via entities rather than the config flow UI.
        """
        existing_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
            # Settings not in UI that should be preserved
            ConfKeys.SIMULATION_MODE.value: True,
            ConfKeys.ENABLED.value: False,
            ConfKeys.VERBOSE_LOGGING.value: True,
            ConfKeys.TEMP_THRESHOLD.value: 25.0,
            ConfKeys.COVERS_MIN_POSITION_DELTA.value: 10,
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Go through all steps without changing covers
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            }
        )

        await flow.async_step_2(
            {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            }
        )

        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 25,  # Changed from 20
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 2, "minutes": 0, "seconds": 0},
            }
        )

        # Step 4: Continue (proceeds to step 5)
        await flow.async_step_4({})

        # Step 5: Continue (proceeds to step 6)
        await flow.async_step_5({})

        # Step 6: Complete flow
        result = await flow.async_step_6({})

        data = _as_dict(result)["data"]

        # Verify settings that were in the UI were updated
        assert data[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == 25

        # Verify settings that were NOT in the UI were preserved
        assert data[ConfKeys.SIMULATION_MODE.value] is True
        assert data[ConfKeys.ENABLED.value] is False
        assert data[ConfKeys.VERBOSE_LOGGING.value] is True
        assert data[ConfKeys.TEMP_THRESHOLD.value] == 25.0
        assert data[ConfKeys.COVERS_MIN_POSITION_DELTA.value] == 10

    async def test_removes_orphaned_max_closure_settings(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that per-cover max_closure settings are removed when covers are removed.

        This exercises the cleanup logic in async_step_4 for max_closure suffixes
        (lines 493-495).
        """
        existing_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,
            # Per-cover max_closure settings that should be cleaned up
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}": 75,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_MAX_CLOSURE}": 85,
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Step 1: Remove MOCK_COVER_ENTITY_ID_2
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],  # Only one cover
            }
        )

        await flow.async_step_2(
            {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            }
        )

        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 2, "minutes": 0, "seconds": 0},
            }
        )

        # Step 4: Continue (proceeds to step 5)
        await flow.async_step_4({})

        # Step 5: Continue (proceeds to step 6)
        await flow.async_step_5({})

        # Step 6: Complete flow
        result = await flow.async_step_6({})

        data = _as_dict(result)["data"]

        # First cover's settings should remain
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in data
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}" in data

        # Second cover's settings should be removed
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}" not in data
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_MAX_CLOSURE}" not in data

    async def test_removes_orphaned_min_closure_settings(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that per-cover min_closure settings are removed when covers are removed.

        This exercises the cleanup logic in async_step_4 for min_closure suffixes
        (lines 497-499).
        """
        existing_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,
            # Per-cover min_closure settings that should be cleaned up
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MIN_CLOSURE}": 15,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_MIN_CLOSURE}": 25,
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Step 1: Remove MOCK_COVER_ENTITY_ID_2
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],  # Only one cover
            }
        )

        await flow.async_step_2(
            {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            }
        )

        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 2, "minutes": 0, "seconds": 0},
            }
        )

        # Step 4: Continue (proceeds to step 5)
        await flow.async_step_4({})

        # Step 5: Continue (proceeds to step 6)
        await flow.async_step_5({})

        # Step 6: Complete flow
        result = await flow.async_step_6({})

        data = _as_dict(result)["data"]

        # First cover's settings should remain
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in data
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MIN_CLOSURE}" in data

        # Second cover's settings should be removed
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}" not in data
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_MIN_CLOSURE}" not in data

    async def test_clearing_per_cover_min_removes_from_options(self, mock_hass_with_covers: MagicMock, caplog: Any) -> None:
        """Clearing a per-cover minimum removes it from saved options and logs it as removed."""
        import logging

        cover = MOCK_COVER_ENTITY_ID
        existing_data = {
            ConfKeys.COVERS.value: [cover],
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            f"{cover}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{cover}_{const.COVER_SFX_MIN_CLOSURE}": 12,
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        with caplog.at_level(logging.INFO, logger="custom_components.smart_cover_automation"):
            await flow.async_step_init(
                {
                    ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                    ConfKeys.COVERS.value: [cover],
                }
            )

            await flow.async_step_2(
                {
                    f"{cover}_{const.COVER_SFX_AZIMUTH}": 180.0,
                }
            )

            await flow.async_step_3(
                {
                    ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
                    ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                    ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                    ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                    ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                }
            )

            # Step 4: Continue with cleared section (proceeds to step 5)
            await flow.async_step_4({"section_min_closure": {}})

            # Step 5: Continue (proceeds to step 6)
            await flow.async_step_5({})

            # Step 6: Complete flow
            result = await flow.async_step_6({})

            # Verify that the cleared setting was logged as removed
            assert "1 removed settings:" in caplog.text
            assert f"{cover}_cover_min_closure" in caplog.text

        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        saved_data = result_dict["data"]

        # Options payload should not include the cleared per-cover minimum
        assert f"{cover}_{const.COVER_SFX_MIN_CLOSURE}" not in saved_data

    async def test_clearing_per_cover_min_with_none_section(self, mock_hass_with_covers: MagicMock) -> None:
        """Section returning None still triggers cleanup of per-cover minimum."""

        cover = MOCK_COVER_ENTITY_ID
        existing_data = {
            ConfKeys.COVERS.value: [cover],
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            f"{cover}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{cover}_{const.COVER_SFX_MIN_CLOSURE}": 12,
        }
        mock_entry = _create_mock_entry(data=existing_data)

        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [cover],
            }
        )

        await flow.async_step_2(
            {
                f"{cover}_{const.COVER_SFX_AZIMUTH}": 180.0,
            }
        )

        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            }
        )

        # Step 4: Continue with None section (proceeds to step 5)
        await flow.async_step_4({"section_min_closure": None})

        # Step 5: Continue (proceeds to step 6)
        await flow.async_step_5({})

        # Step 6: Complete flow
        result = await flow.async_step_6({})
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        saved_data = result_dict["data"]

        # Options payload should not include the cleared per-cover minimum
        assert f"{cover}_{const.COVER_SFX_MIN_CLOSURE}" not in saved_data


class TestOptionsFlowHelperMethods:
    """Test private helper methods of OptionsFlowHandler."""

    def test_is_empty_value_with_none(self) -> None:
        """Test _is_empty_value returns True for None."""
        from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

        assert OptionsFlowHandler._is_empty_value(None) is True

    def test_is_empty_value_with_empty_string(self) -> None:
        """Test _is_empty_value returns True for empty string."""
        from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

        assert OptionsFlowHandler._is_empty_value("") is True

    def test_is_empty_value_with_undefined(self) -> None:
        """Test _is_empty_value returns True for vol.UNDEFINED."""
        import voluptuous as vol

        from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

        assert OptionsFlowHandler._is_empty_value(vol.UNDEFINED) is True

    def test_is_empty_value_with_valid_value(self) -> None:
        """Test _is_empty_value returns False for valid values."""
        from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

        assert OptionsFlowHandler._is_empty_value(0) is False
        assert OptionsFlowHandler._is_empty_value("test") is False
        assert OptionsFlowHandler._is_empty_value(123) is False

    def test_to_int_with_empty_value(self) -> None:
        """Test _to_int returns None for empty values."""
        from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

        assert OptionsFlowHandler._to_int(None) is None
        assert OptionsFlowHandler._to_int("") is None

    def test_to_int_with_valid_int(self) -> None:
        """Test _to_int converts valid integers."""
        from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

        assert OptionsFlowHandler._to_int(42) == 42
        assert OptionsFlowHandler._to_int("100") == 100

    def test_build_section_cover_settings_with_missing_key(self) -> None:
        """Test _build_section_cover_settings when key is not in user input."""
        from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

        user_input = {
            const.STEP_4_SECTION_MAX_CLOSURE: {
                # Only one cover present
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}": 90,
            }
        }

        # Request settings for two covers, but only one is in input
        covers = [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2]

        # Empty current settings
        current_settings: dict[str, Any] = {}

        result = OptionsFlowHandler._build_section_cover_settings(
            user_input, const.STEP_4_SECTION_MAX_CLOSURE, const.COVER_SFX_MAX_CLOSURE, covers, current_settings
        )

        # First cover should have the value
        assert result[f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}"] == 90
        # Second cover should NOT be in result (was not modified)
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_MAX_CLOSURE}" not in result

    async def test_options_flow_no_changes_logs_debug(self, mock_hass_with_covers: MagicMock, caplog: Any) -> None:
        """Test that completing flow with no changes logs at debug level."""
        import logging

        # Use dict format for manual_override_duration so it matches what the form returns
        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.TEMP_THRESHOLD.value: 23,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        }
        mock_entry = _create_mock_entry(data=existing_data)
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Go through all steps with same data (no changes)
        with caplog.at_level(logging.DEBUG, logger="custom_components.smart_cover_automation"):
            await flow.async_step_init(
                {
                    ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                    ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
                }
            )

            await flow.async_step_2({f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0})

            await flow.async_step_3(
                {
                    ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
                    ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                    ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                    ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                    ConfKeys.TEMP_THRESHOLD.value: 23,
                    ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                }
            )

            await flow.async_step_4({})

            # Step 5: Continue (proceeds to step 6)
            await flow.async_step_5({})

            # Step 6: Complete flow
            result = await flow.async_step_6({})

            # Check that info messages were logged for no changes
            assert "Options flow: No changed settings" in caplog.text
            assert "Options flow: No new settings" in caplog.text
            assert "Options flow: No removed settings" in caplog.text

        result_dict = _as_dict(result)
        assert result_dict["type"] == FlowResultType.CREATE_ENTRY

    #
    # test_options_flow_with_changed_settings_logs_info
    #
    async def test_options_flow_with_changed_settings_logs_info(self, mock_hass_with_covers: MagicMock, caplog: Any) -> None:
        """Test that completing flow with changed settings logs them at info level."""
        import logging

        # Start with existing data
        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.TEMP_THRESHOLD.value: 23,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        }
        mock_entry = _create_mock_entry(data=existing_data)
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Go through flow and change temperature threshold and sun elevation
        with caplog.at_level(logging.INFO, logger="custom_components.smart_cover_automation"):
            await flow.async_step_init(
                {
                    ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                    ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
                }
            )

            await flow.async_step_2({f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0})

            # Change temp_threshold from 23 to 25 and sun_elevation_threshold from 5 to 10
            await flow.async_step_3(
                {
                    ConfKeys.SUN_ELEVATION_THRESHOLD.value: 10,  # Changed from 5
                    ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                    ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                    ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                    ConfKeys.TEMP_THRESHOLD.value: 25,  # Changed from 23
                    ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
                }
            )

            await flow.async_step_4({})
            await flow.async_step_5({})
            result = await flow.async_step_6({})

            # Check that changed settings were logged
            assert "2 changed settings:" in caplog.text
            assert "temp_threshold" in caplog.text
            assert "sun_elevation_threshold" in caplog.text

        result_dict = _as_dict(result)
        assert result_dict["type"] == FlowResultType.CREATE_ENTRY


class TestOptionsFlowStep6CloseAfterSunset:
    """Test step 6 close_after_sunset section functionality."""

    #
    # test_step_6_schema_includes_close_after_sunset_section
    #
    async def test_step_6_schema_includes_close_after_sunset_section(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 6 schema includes all three close_after_sunset fields."""

        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        }
        mock_entry = _create_mock_entry(data=existing_data)
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Navigate to step 6
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            }
        )
        await flow.async_step_2({f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0})
        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            }
        )
        await flow.async_step_4({})
        await flow.async_step_5({})

        # Get step 6 form
        result = await flow.async_step_6()
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "6"

        # Verify schema contains the section
        schema = result_dict["data_schema"]
        schema_keys = [str(key) for key in schema.schema.keys()]

        # The section itself should be in schema
        assert any(const.STEP_6_SECTION_CLOSE_AFTER_SUNSET in key for key in schema_keys)

    #
    # test_step_6_saves_close_after_sunset_settings
    #
    async def test_step_6_saves_close_after_sunset_settings(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that all three close_after_sunset settings are saved correctly."""

        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        }
        mock_entry = _create_mock_entry(data=existing_data)
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Navigate to step 6
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            }
        )
        await flow.async_step_2(
            {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
                f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,
            }
        )
        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            }
        )
        await flow.async_step_4({})
        await flow.async_step_5({})

        # Submit step 6 with close_after_sunset settings
        user_input = {
            const.STEP_6_SECTION_CLOSE_AFTER_SUNSET: {
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 1, "minutes": 30, "seconds": 0},
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: [MOCK_COVER_ENTITY_ID],
            }
        }

        result = await flow.async_step_6(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        saved_data = result_dict["data"]

        # Verify all three settings are saved correctly
        assert saved_data[ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value] is True
        assert saved_data[ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value] == {"hours": 1, "minutes": 30, "seconds": 0}
        assert saved_data[ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value] == [MOCK_COVER_ENTITY_ID]

    #
    # test_step_6_close_after_sunset_disabled
    #
    async def test_step_6_close_after_sunset_disabled(self, mock_hass_with_covers: MagicMock) -> None:
        """Test disabling close_after_sunset feature."""

        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,  # Previously enabled
        }
        mock_entry = _create_mock_entry(data=existing_data)
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Navigate to step 6
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            }
        )
        await flow.async_step_2({f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0})
        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            }
        )
        await flow.async_step_4({})
        await flow.async_step_5({})

        # Submit step 6 with close_after_sunset disabled
        user_input = {
            const.STEP_6_SECTION_CLOSE_AFTER_SUNSET: {
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: False,
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 0, "minutes": 15, "seconds": 0},
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: [],
            }
        }

        result = await flow.async_step_6(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        saved_data = result_dict["data"]

        # Verify disabled state is saved
        assert saved_data[ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value] is False

    #
    # test_step_6_close_after_sunset_empty_cover_list
    #
    async def test_step_6_close_after_sunset_empty_cover_list(self, mock_hass_with_covers: MagicMock) -> None:
        """Test saving close_after_sunset with empty cover list."""

        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        }
        mock_entry = _create_mock_entry(data=existing_data)
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Navigate to step 6
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            }
        )
        await flow.async_step_2({f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0})
        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            }
        )
        await flow.async_step_4({})
        await flow.async_step_5({})

        # Submit step 6 with empty cover list
        user_input = {
            const.STEP_6_SECTION_CLOSE_AFTER_SUNSET: {
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 0, "minutes": 15, "seconds": 0},
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: [],  # Empty list
            }
        }

        result = await flow.async_step_6(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        saved_data = result_dict["data"]

        # Verify empty cover list is saved as empty list
        assert saved_data[ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value] == []

    #
    # test_step_6_close_after_sunset_zero_delay
    #
    async def test_step_6_close_after_sunset_zero_delay(self, mock_hass_with_covers: MagicMock) -> None:
        """Test saving close_after_sunset with zero delay (immediate closure)."""

        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        }
        mock_entry = _create_mock_entry(data=existing_data)
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Navigate to step 6
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            }
        )
        await flow.async_step_2({f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0})
        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            }
        )
        await flow.async_step_4({})
        await flow.async_step_5({})

        # Submit step 6 with zero delay
        user_input = {
            const.STEP_6_SECTION_CLOSE_AFTER_SUNSET: {
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 0, "minutes": 0, "seconds": 0},
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: [MOCK_COVER_ENTITY_ID],
            }
        }

        result = await flow.async_step_6(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        saved_data = result_dict["data"]

        # Verify zero delay is saved correctly as a dict
        assert saved_data[ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value] == {"hours": 0, "minutes": 0, "seconds": 0}

    #
    # test_step_6_close_after_sunset_multiple_covers
    #
    async def test_step_6_close_after_sunset_multiple_covers(self, mock_hass_with_covers: MagicMock) -> None:
        """Test saving close_after_sunset with multiple covers selected."""

        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        }
        mock_entry = _create_mock_entry(data=existing_data)
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Navigate to step 6
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            }
        )
        await flow.async_step_2(
            {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
                f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,
            }
        )
        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            }
        )
        await flow.async_step_4({})
        await flow.async_step_5({})

        # Submit step 6 with multiple covers
        user_input = {
            const.STEP_6_SECTION_CLOSE_AFTER_SUNSET: {
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 2, "minutes": 0, "seconds": 30},
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            }
        }

        result = await flow.async_step_6(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        saved_data = result_dict["data"]

        # Verify both covers are in the list
        assert set(saved_data[ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value]) == {
            MOCK_COVER_ENTITY_ID,
            MOCK_COVER_ENTITY_ID_2,
        }
        # Verify delay is saved as dict: 2 hours + 30 seconds
        assert saved_data[ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value] == {"hours": 2, "minutes": 0, "seconds": 30}

    #
    # test_step_6_section_extraction_flattens_correctly
    #
    async def test_step_6_section_extraction_flattens_correctly(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that section extraction correctly flattens nested close_after_sunset data."""

        existing_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 100,
            ConfKeys.COVERS_MIN_CLOSURE.value: 0,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
        }
        mock_entry = _create_mock_entry(data=existing_data)
        flow = OptionsFlowHandler(mock_entry)
        flow.hass = mock_hass_with_covers

        # Navigate to step 6
        await flow.async_step_init(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            }
        )
        await flow.async_step_2({f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0})
        await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 5,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 0, "minutes": 30, "seconds": 0},
            }
        )
        await flow.async_step_4({})
        await flow.async_step_5({})

        # Submit step 6 with nested section data
        user_input = {
            const.STEP_6_SECTION_CLOSE_AFTER_SUNSET: {
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value: True,
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value: {"hours": 1, "minutes": 15, "seconds": 30},
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value: [MOCK_COVER_ENTITY_ID],
            }
        }

        result = await flow.async_step_6(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        saved_data = result_dict["data"]

        # Verify section key is NOT in saved data (should be flattened)
        assert const.STEP_6_SECTION_CLOSE_AFTER_SUNSET not in saved_data

        # Verify all three settings are at top level
        assert ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value in saved_data
        assert ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value in saved_data
        assert ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value in saved_data
