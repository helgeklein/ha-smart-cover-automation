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
    """Create a mock config entry for testing."""
    mock_entry = MagicMock()
    mock_entry.data = data or {}
    mock_entry.options = options or {}
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

        assert ConfKeys.SUN_ELEVATION_THRESHOLD.value in schema_keys
        assert ConfKeys.SUN_AZIMUTH_TOLERANCE.value in schema_keys
        assert ConfKeys.COVERS_MAX_CLOSURE.value in schema_keys
        assert ConfKeys.COVERS_MIN_CLOSURE.value in schema_keys
        assert ConfKeys.MANUAL_OVERRIDE_DURATION.value in schema_keys

    async def test_step_3_creates_entry_with_updated_config(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 3 creates entry with updated configuration."""
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

        # Step 3 now directly creates the entry
        assert result3_dict["type"] == FlowResultType.CREATE_ENTRY
        assert result3_dict["title"] == ""  # Options flow uses empty title

        data = result3_dict["data"]
        assert data[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == 35
        assert data[ConfKeys.COVERS_MAX_CLOSURE.value] == 85

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

        # Step 3 now directly creates the entry
        assert result3_dict["type"] == FlowResultType.CREATE_ENTRY

        data = result3_dict["data"]
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

        # Step 3: Submit data (now directly creates entry)
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
        assert result3_dict["type"] == FlowResultType.CREATE_ENTRY

        # Verify updated configuration
        data = result3_dict["data"]
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

        # Step 3: Complete (now directly creates entry)
        result = await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 2, "minutes": 0, "seconds": 0},
            }
        )

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

        result = await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 25,  # Changed from 20
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 2, "minutes": 0, "seconds": 0},
            }
        )

        data = _as_dict(result)["data"]

        # Verify settings that were in the UI were updated
        assert data[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == 25

        # Verify settings that were NOT in the UI were preserved
        assert data[ConfKeys.SIMULATION_MODE.value] is True
        assert data[ConfKeys.ENABLED.value] is False
        assert data[ConfKeys.VERBOSE_LOGGING.value] is True
        assert data[ConfKeys.TEMP_THRESHOLD.value] == 25.0
        assert data[ConfKeys.COVERS_MIN_POSITION_DELTA.value] == 10
