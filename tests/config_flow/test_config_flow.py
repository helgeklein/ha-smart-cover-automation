"""Tests for the Smart Cover Automation config flow.

This module tests the initial configuration flow for setting up the integration.
The flow has 3 steps:
1. Cover and weather entity selection
2. Azimuth configuration per cover
3. Sun position, cover behavior, and manual override settings
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.data_entry_flow import FlowResultType

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.config_flow import FlowHandler

from ..conftest import MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2, MOCK_WEATHER_ENTITY_ID


def _as_dict(result: ConfigFlowResult) -> dict[str, Any]:
    """Convert ConfigFlowResult to dictionary for test assertions."""
    return cast(dict[str, Any], result)


class TestConfigFlowStep1:
    """Test step 1: Cover and weather entity selection."""

    async def test_step_user_shows_form_initially(self) -> None:
        """Test that step 1 shows the menu on initial call."""
        flow = FlowHandler()

        result = await flow.async_step_user(None)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.MENU
        assert result_dict["step_id"] == "user"
        assert "menu_options" in result_dict

    async def test_step_user_validates_and_proceeds_to_step2(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that valid input in step 1 proceeds to step 2."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        result = await flow.async_step_user(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "2"  # Proceeds to step 2
        assert ConfKeys.WEATHER_ENTITY_ID.value in flow._config_data
        assert ConfKeys.COVERS.value in flow._config_data

    async def test_step_user_error_no_covers(self, mock_hass_with_covers: MagicMock) -> None:
        """Test error when no covers are selected."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [],
        }

        result = await flow.async_step_user(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "user_form"
        assert ConfKeys.COVERS.value in result_dict["errors"]
        assert result_dict["errors"][ConfKeys.COVERS.value] == const.ERROR_NO_COVERS

    async def test_step_user_error_invalid_cover(self, mock_hass_with_covers: MagicMock) -> None:
        """Test error when invalid cover entity is selected."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers

        # Override the mock to return None for the specific non-existent cover
        def mock_get_state(entity_id: str) -> MagicMock | None:
            if entity_id == "cover.nonexistent":
                return None  # Entity doesn't exist
            if entity_id.startswith("cover."):
                return MagicMock(state="closed")
            if entity_id.startswith("weather."):
                from homeassistant.components.weather.const import WeatherEntityFeature

                weather_state = MagicMock()
                weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}
                return weather_state
            return None

        mock_hass_with_covers.states.get.side_effect = mock_get_state

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: ["cover.nonexistent"],
        }

        result = await flow.async_step_user(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "user_form"
        assert ConfKeys.COVERS.value in result_dict["errors"]
        assert result_dict["errors"][ConfKeys.COVERS.value] == const.ERROR_INVALID_COVER

    async def test_step_user_error_no_weather_entity(self, mock_hass_with_covers: MagicMock) -> None:
        """Test error when no weather entity is selected."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: "",
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        result = await flow.async_step_user(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "user_form"
        assert ConfKeys.WEATHER_ENTITY_ID.value in result_dict["errors"]
        assert result_dict["errors"][ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_NO_WEATHER_ENTITY

    async def test_step_user_error_invalid_weather_entity(self, mock_hass_with_covers: MagicMock) -> None:
        """Test error when weather entity doesn't support daily forecasts."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers

        # Override the mock to return weather entity without daily forecast support
        def mock_get_state(entity_id: str) -> MagicMock | None:
            if entity_id == "weather.no_forecast":
                weather_state = MagicMock()
                weather_state.attributes = {"supported_features": 0}  # No features
                return weather_state
            if entity_id.startswith("cover."):
                return MagicMock(state="closed")
            if entity_id.startswith("weather."):
                from homeassistant.components.weather.const import WeatherEntityFeature

                weather_state = MagicMock()
                weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}
                return weather_state
            return None

        mock_hass_with_covers.states.get.side_effect = mock_get_state

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.no_forecast",
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        result = await flow.async_step_user(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "user_form"
        assert ConfKeys.WEATHER_ENTITY_ID.value in result_dict["errors"]
        assert result_dict["errors"][ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_INVALID_WEATHER_ENTITY

    async def test_step_user_allows_unavailable_cover(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that unavailable cover is still allowed to be configured."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers

        # Override the mock to return unavailable cover
        def mock_get_state(entity_id: str) -> MagicMock | None:
            if entity_id == "cover.unavailable":
                cover_state = MagicMock()
                cover_state.state = STATE_UNAVAILABLE
                return cover_state
            if entity_id.startswith("cover."):
                return MagicMock(state="closed")
            if entity_id.startswith("weather."):
                from homeassistant.components.weather.const import WeatherEntityFeature

                weather_state = MagicMock()
                weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}
                return weather_state
            return None

        mock_hass_with_covers.states.get.side_effect = mock_get_state

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: ["cover.unavailable"],
        }

        result = await flow.async_step_user(user_input)
        result_dict = _as_dict(result)

        # Should proceed (not fail) even though cover is unavailable
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "2"
        # Cover should be in config data
        assert "cover.unavailable" in flow._config_data[ConfKeys.COVERS.value]

    async def test_step_user_form_delegates_to_user(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that async_step_user_form delegates to async_step_user."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        result = await flow.async_step_user_form(user_input)
        result_dict = _as_dict(result)

        # Should delegate to async_step_user and proceed to step 2
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "2"

    async def test_step_user_shows_form_when_called_from_menu(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that async_step_user shows form when called from menu click."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers
        # Simulate that menu was already shown
        flow._menu_shown = True

        # Call with None (simulates menu click)
        result = await flow.async_step_user(None)
        result_dict = _as_dict(result)

        # Should show the form, not the menu again
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "user_form"


class TestConfigFlowStep2:
    """Test step 2: Azimuth configuration per cover."""

    async def test_step_2_shows_form_with_cover_fields(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 2 shows azimuth fields for each cover."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers
        flow._config_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
        }

        result = await flow.async_step_2(None)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "2"

        # Check that schema has azimuth fields for both covers
        schema = result_dict["data_schema"].schema
        azimuth_key_1 = f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}"
        azimuth_key_2 = f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}"

        # Schema keys are voluptuous markers, need to extract the schema values
        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.keys()]
        assert azimuth_key_1 in schema_keys
        assert azimuth_key_2 in schema_keys

    async def test_step_2_proceeds_to_step3_with_valid_input(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that valid azimuth input proceeds to step 3."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers
        flow._config_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        user_input = {
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
        }

        result = await flow.async_step_2(user_input)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.MENU
        assert "menu_options" in result_dict
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in flow._config_data


class TestConfigFlowStep3:
    """Test step 3: Sun position, cover behavior, and manual override settings."""

    async def test_step_3_shows_form_with_all_settings(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 3 shows all final settings."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers
        flow._config_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
        }

        result = await flow.async_step_3(None)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "3"

        # Check that schema has all expected fields
        schema = result_dict["data_schema"].schema
        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.keys()]

        assert ConfKeys.SUN_ELEVATION_THRESHOLD.value in schema_keys
        assert ConfKeys.SUN_AZIMUTH_TOLERANCE.value in schema_keys
        assert ConfKeys.COVERS_MAX_CLOSURE.value in schema_keys
        assert ConfKeys.COVERS_MIN_CLOSURE.value in schema_keys
        assert ConfKeys.MANUAL_OVERRIDE_DURATION.value in schema_keys

    async def test_step_3_creates_entry_with_complete_config(self, mock_hass_with_covers: MagicMock) -> None:
        """Test that step 3 creates config entry with all data."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers
        flow._config_data = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
        }

        user_input = {
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 30,
            ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
            ConfKeys.COVERS_MAX_CLOSURE.value: 80,
            ConfKeys.COVERS_MIN_CLOSURE.value: 20,
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 1, "minutes": 30, "seconds": 0},
        }

        result = await flow.async_step_3(user_input)
        result_dict = _as_dict(result)

        # Step 3 now returns to menu with submit option
        assert result_dict["type"] == FlowResultType.MENU
        assert "menu_options" in result_dict
        assert "submit" in result_dict["menu_options"]

        # Now call submit step to create entry
        result = await flow.async_step_submit(None)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        assert result_dict["title"] == const.INTEGRATION_NAME

        # Verify all data was merged
        data = result_dict["data"]
        assert data[ConfKeys.WEATHER_ENTITY_ID.value] == MOCK_WEATHER_ENTITY_ID
        assert data[ConfKeys.COVERS.value] == [MOCK_COVER_ENTITY_ID]
        assert data[f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}"] == 180.0
        assert data[ConfKeys.SUN_ELEVATION_THRESHOLD.value] == 30
        assert data[ConfKeys.SUN_AZIMUTH_TOLERANCE.value] == 90
        assert data[ConfKeys.COVERS_MAX_CLOSURE.value] == 80
        assert data[ConfKeys.COVERS_MIN_CLOSURE.value] == 20


class TestConfigFlowIntegration:
    """Test complete flow from start to finish."""

    async def test_complete_flow_single_cover(self, mock_hass_with_covers: MagicMock) -> None:
        """Test complete 3-step flow with a single cover."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers

        # Step 1: Cover and weather selection
        result1 = await flow.async_step_user(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            }
        )
        assert _as_dict(result1)["type"] == FlowResultType.FORM
        assert _as_dict(result1)["step_id"] == "2"

        # Step 2: Azimuth configuration
        result2 = await flow.async_step_2(
            {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            }
        )
        assert _as_dict(result2)["type"] == FlowResultType.MENU
        assert "menu_options" in _as_dict(result2)
        assert "3" in _as_dict(result2)["menu_options"]

        # Step 3: Final settings
        result3 = await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 90,
                ConfKeys.COVERS_MAX_CLOSURE.value: 100,
                ConfKeys.COVERS_MIN_CLOSURE.value: 0,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 2, "minutes": 0, "seconds": 0},
            }
        )
        assert _as_dict(result3)["type"] == FlowResultType.MENU
        assert "submit" in _as_dict(result3)["menu_options"]

        # Submit: Create entry
        result4 = await flow.async_step_submit(None)
        assert _as_dict(result4)["type"] == FlowResultType.CREATE_ENTRY

    async def test_complete_flow_multiple_covers(self, mock_hass_with_covers: MagicMock) -> None:
        """Test complete 3-step flow with multiple covers."""
        flow = FlowHandler()
        flow.hass = mock_hass_with_covers

        # Step 1
        result1 = await flow.async_step_user(
            {
                ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
                ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            }
        )
        assert _as_dict(result1)["step_id"] == "2"

        # Step 2: Configure azimuth for both covers
        result2 = await flow.async_step_2(
            {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
                f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,
            }
        )
        assert _as_dict(result2)["type"] == FlowResultType.MENU
        assert "menu_options" in _as_dict(result2)

        # Step 3
        result3 = await flow.async_step_3(
            {
                ConfKeys.SUN_ELEVATION_THRESHOLD.value: 25,
                ConfKeys.SUN_AZIMUTH_TOLERANCE.value: 85,
                ConfKeys.COVERS_MAX_CLOSURE.value: 90,
                ConfKeys.COVERS_MIN_CLOSURE.value: 10,
                ConfKeys.MANUAL_OVERRIDE_DURATION.value: {"hours": 1, "minutes": 0, "seconds": 0},
            }
        )

        result_dict = _as_dict(result3)
        assert result_dict["type"] == FlowResultType.MENU
        assert "submit" in result_dict["menu_options"]

        # Submit to create entry
        result4 = await flow.async_step_submit(None)
        result_dict = _as_dict(result4)
        assert result_dict["type"] == FlowResultType.CREATE_ENTRY

        # Verify both covers' azimuths are in the final data
        data = result_dict["data"]
        assert data[f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}"] == 180.0
        assert data[f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}"] == 90.0


class TestConfigFlowStaticMethod:
    """Test the static method for creating options flow."""

    def test_async_get_options_flow(self) -> None:
        """Test that the static method returns an OptionsFlowHandler."""
        from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

        mock_entry = MagicMock()
        mock_entry.data = {ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID]}

        result = FlowHandler.async_get_options_flow(mock_entry)

        assert isinstance(result, OptionsFlowHandler)
        assert result._config_entry == mock_entry
