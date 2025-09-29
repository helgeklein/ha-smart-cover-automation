"""Extended tests for the Smart Cover Automation config flow.

This module contains additional tests to improve config flow test coverage,
focusing on edge cases and less commonly tested code paths including:
- Weather entity validation with forecast feature checking
- Options flow weather validation and abort scenarios
- Cover cleanup logic in options flow when covers are removed
- Error handling for weather entities without proper features
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock, patch

from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.data_entry_flow import FlowResultType

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.config_flow import FlowHandler, OptionsFlowHandler

from .conftest import (
    MOCK_COVER_ENTITY_ID,
    MOCK_COVER_ENTITY_ID_2,
    create_mock_state_getter,
)


class TestConfigFlowWeatherValidation:
    """Test weather entity validation in the main config flow."""

    @staticmethod
    def _as_dict(result: object) -> dict[str, Any]:
        """Convert ConfigFlowResult to dictionary for test assertions."""
        return cast(dict[str, Any], result)

    async def test_weather_entity_invalid_features(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test config flow error when weather entity lacks daily forecast support.

        This tests the weather entity validation logic that checks for
        WeatherEntityFeature.FORECAST_DAILY support. Weather entities without
        this feature cannot provide the daily forecast data needed for automation.
        """
        # Setup weather entity that exists but lacks forecast daily feature
        weather_state = MagicMock()
        weather_state.attributes = {"supported_features": 0}  # No forecast features

        # Create state mappings
        cover_states = {entity_id: MagicMock(state="closed") for entity_id in [MOCK_COVER_ENTITY_ID] if entity_id.startswith("cover.")}

        # Mock hass to return covers and invalid weather entity
        mock_hass_with_covers.states.get.side_effect = create_mock_state_getter(**cover_states, **{"weather.test": weather_state})
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        }

        result = await flow_handler.async_step_user(user_input)
        result_dict = self._as_dict(result)

        # Should return form with error
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["errors"]["base"] == const.ERROR_INVALID_WEATHER_ENTITY

    async def test_weather_entity_not_found(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test config flow error when weather entity doesn't exist.

        This tests the case where a user provides a weather entity ID that
        doesn't exist in the Home Assistant state registry.
        """

        # Mock hass to return no weather entities and one cover entity
        mock_hass_with_covers.states.get.side_effect = create_mock_state_getter(
            **{entity_id: MagicMock(state="closed") for entity_id in [MOCK_COVER_ENTITY_ID] if entity_id.startswith("cover.")}
        )
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.nonexistent",
        }

        result = await flow_handler.async_step_user(user_input)
        result_dict = self._as_dict(result)

        # Should return form with error
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["errors"]["base"] == const.ERROR_INVALID_WEATHER_ENTITY

    async def test_weather_entity_valid_features(
        self,
        flow_handler: FlowHandler,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test config flow success when weather entity has valid forecast features.

        This tests the positive case where weather entity validation passes
        because the entity has the required FORECAST_DAILY feature.
        """
        # Setup weather entity with valid forecast daily feature
        weather_state = MagicMock()
        weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}

        # Create state mappings
        cover_states = {entity_id: MagicMock(state="closed") for entity_id in [MOCK_COVER_ENTITY_ID] if entity_id.startswith("cover.")}

        # Mock hass to return covers and valid weather entity
        mock_hass_with_covers.states.get.side_effect = create_mock_state_getter(**cover_states, **{"weather.valid": weather_state})
        flow_handler.hass = mock_hass_with_covers

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.valid",
        }

        # Mock unique ID operations
        with (
            patch.object(flow_handler, "async_set_unique_id"),
            patch.object(flow_handler, "_abort_if_unique_id_configured"),
        ):
            result = await flow_handler.async_step_user(user_input)
            result_dict = self._as_dict(result)

            # Should succeed and create entry
            assert result_dict["type"] == FlowResultType.CREATE_ENTRY
            assert result_dict["data"] == user_input


class TestOptionsFlowExtended:
    """Test options flow functionality with comprehensive coverage."""

    @staticmethod
    def _as_dict(result: object) -> dict[str, Any]:
        """Convert ConfigFlowResult to dictionary for test assertions."""
        return cast(dict[str, Any], result)

    async def test_options_flow_weather_entity_invalid_features_abort(
        self,
        mock_config_entry_extended: MagicMock,
        mock_hass_with_weather_and_covers: MagicMock,
    ) -> None:
        """Test options flow aborts when weather entity lacks forecast features.

        This tests the options flow validation logic that prevents saving
        options with an invalid weather entity. When a user selects a weather
        entity without daily forecast support, the flow should abort with an error.
        """
        mock_config_entry_extended.hass = mock_hass_with_weather_and_covers

        # Create cover states
        cover_states = {}
        for entity_id in [MOCK_COVER_ENTITY_ID]:
            if entity_id.startswith("cover."):
                state = MagicMock()
                state.name = f"Test Cover {entity_id.split('.')[-1]}"
                cover_states[entity_id] = state

        # Create invalid weather state
        invalid_weather_state = MagicMock()
        invalid_weather_state.attributes = {"supported_features": 0}  # No forecast features

        # Override weather entity to have invalid features
        mock_hass_with_weather_and_covers.states.get.side_effect = create_mock_state_getter(
            **cover_states, **{"weather.invalid": invalid_weather_state}
        )

        options_flow = OptionsFlowHandler(mock_config_entry_extended)

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.invalid",
            ConfKeys.ENABLED.value: True,
        }

        result = await options_flow.async_step_init(user_input)
        result_dict = self._as_dict(result)

        # Should abort with weather entity error
        assert result_dict["type"] == FlowResultType.ABORT
        assert result_dict["reason"] == const.ERROR_INVALID_WEATHER_ENTITY

    async def test_options_flow_cover_cleanup_when_covers_modified(
        self,
        mock_config_entry_extended: MagicMock,
        mock_hass_with_weather_and_covers: MagicMock,
    ) -> None:
        """Test options flow cleans up azimuth settings for removed covers.

        This tests the cover cleanup logic that removes azimuth configuration
        for covers that are no longer in the covers list. When users remove
        covers from the configuration, their azimuth settings should be cleaned up.
        """
        mock_config_entry_extended.hass = mock_hass_with_weather_and_covers
        options_flow = OptionsFlowHandler(mock_config_entry_extended)

        # User input that removes one of the covers but keeps azimuth settings
        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],  # Remove MOCK_COVER_ENTITY_ID_2
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.ENABLED.value: True,
            # Keep both azimuth settings even though one cover is removed
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}": 90.0,  # This should be cleaned up
        }

        result = await options_flow.async_step_init(user_input)
        result_dict = self._as_dict(result)

        # Should succeed and create entry with cleaned data
        assert result_dict["type"] == FlowResultType.CREATE_ENTRY

        # Verify the orphaned azimuth setting was removed
        expected_data = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            ConfKeys.ENABLED.value: True,
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 180.0,
            # f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}" should be removed
        }
        assert result_dict["data"] == expected_data
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}" not in result_dict["data"]

    async def test_options_flow_no_cleanup_when_covers_not_modified(
        self,
        mock_config_entry_extended: MagicMock,
        mock_hass_with_weather_and_covers: MagicMock,
    ) -> None:
        """Test options flow skips cleanup when covers list is not modified.

        This tests that the cleanup logic is only triggered when the user
        actually modifies the covers list. If they only change other settings,
        no cleanup should occur.
        """
        mock_config_entry_extended.hass = mock_hass_with_weather_and_covers
        options_flow = OptionsFlowHandler(mock_config_entry_extended)

        # User input that doesn't modify covers list
        user_input = {
            ConfKeys.ENABLED.value: False,  # Only change enabled setting
            ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
            # Don't include covers in user_input to simulate not modifying them
        }

        result = await options_flow.async_step_init(user_input)
        result_dict = self._as_dict(result)

        # Should succeed without cleanup
        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        assert result_dict["data"] == user_input

    async def test_options_flow_initial_form_display(
        self,
        mock_config_entry_extended: MagicMock,
        mock_hass_with_weather_and_covers: MagicMock,
    ) -> None:
        """Test options flow displays form correctly on initial call.

        This tests that the options flow properly constructs and displays
        the form with current configuration values as defaults.
        """
        mock_config_entry_extended.hass = mock_hass_with_weather_and_covers
        options_flow = OptionsFlowHandler(mock_config_entry_extended)

        # Initial call with no user input should show form
        result = await options_flow.async_step_init(None)
        result_dict = self._as_dict(result)

        # Should display form
        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "init"

        # Verify form has expected fields
        schema_keys = list(result_dict["data_schema"].schema.keys())
        schema_key_values = [key.schema for key in schema_keys]

        assert ConfKeys.ENABLED.value in schema_key_values
        assert ConfKeys.COVERS.value in schema_key_values
        assert ConfKeys.WEATHER_ENTITY_ID.value in schema_key_values
