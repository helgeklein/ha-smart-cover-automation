"""Test config flow coverage to achieve 100% coverage for config_flow.py."""

from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.weather import WeatherEntityFeature
from homeassistant.data_entry_flow import FlowResultType

from custom_components.smart_cover_automation.config_flow import FlowHandler, OptionsFlowHandler
from custom_components.smart_cover_automation.const import ERROR_INVALID_CONFIG

from ..conftest import MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2

# Mock weather entity ID for testing
MOCK_WEATHER_ENTITY_ID = "weather.test"


class TestConfigFlowCoverage:
    """Test class for config flow coverage improvements."""

    async def test_exception_handling_in_async_step_user(
        self,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test exception handling for KeyError, ValueError, TypeError in async_step_user.

        This test covers lines 91-93 in config_flow.py by triggering an exception
        during config validation that gets caught by the except block.
        """
        flow_handler = FlowHandler()
        flow_handler.hass = mock_hass_with_covers

        # Mock weather entity validation to pass, but return different values based on call
        def mock_states_get(entity_id):
            if entity_id == MOCK_WEATHER_ENTITY_ID:
                # Valid weather entity for weather validation
                mock_weather_state = MagicMock()
                mock_weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}
                return mock_weather_state
            else:
                # Valid cover entities
                mock_cover_state = MagicMock()
                mock_cover_state.attributes = {"supported_features": 15}
                return mock_cover_state

        mock_hass_with_covers.states.get.side_effect = mock_states_get

        # Create user input with valid covers and weather entity
        user_input = {
            "covers": [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2],
            "weather_entity_id": MOCK_WEATHER_ENTITY_ID,
        }

        # Patch the async_create_entry method to raise a ValueError during validation
        with patch.object(flow_handler, "async_create_entry") as mock_create_entry:
            mock_create_entry.side_effect = ValueError("Test validation error")

            # Execute config flow with input that triggers the exception
            result = await flow_handler.async_step_user(user_input)
            result_dict = cast(dict[str, Any], result)

            # Verify error handling returns to form with appropriate error message
            assert result_dict["type"] == FlowResultType.FORM
            assert result_dict["errors"]["base"] == ERROR_INVALID_CONFIG

    async def test_exception_handling_key_error(
        self,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test exception handling for KeyError specifically.

        This test covers lines 91-93 in config_flow.py by triggering a KeyError
        during config validation.
        """
        flow_handler = FlowHandler()
        flow_handler.hass = mock_hass_with_covers

        # Mock weather entity validation to pass, but return different values based on call
        def mock_states_get(entity_id):
            if entity_id == MOCK_WEATHER_ENTITY_ID:
                # Valid weather entity for weather validation
                mock_weather_state = MagicMock()
                mock_weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}
                return mock_weather_state
            else:
                # Valid cover entities
                mock_cover_state = MagicMock()
                mock_cover_state.attributes = {"supported_features": 15}
                return mock_cover_state

        mock_hass_with_covers.states.get.side_effect = mock_states_get

        # Create user input
        user_input = {
            "covers": [MOCK_COVER_ENTITY_ID],
            "weather_entity_id": MOCK_WEATHER_ENTITY_ID,
        }

        # Patch the async_create_entry method to raise a KeyError during validation
        with patch.object(flow_handler, "async_create_entry") as mock_create_entry:
            mock_create_entry.side_effect = KeyError("Test key error")

            # Execute config flow with input that triggers the exception
            result = await flow_handler.async_step_user(user_input)
            result_dict = cast(dict[str, Any], result)

            # Verify error handling returns to form with appropriate error message
            assert result_dict["type"] == FlowResultType.FORM
            assert result_dict["errors"]["base"] == ERROR_INVALID_CONFIG

    async def test_exception_handling_type_error(
        self,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test exception handling for TypeError specifically.

        This test covers lines 91-93 in config_flow.py by triggering a TypeError
        during config validation.
        """
        flow_handler = FlowHandler()
        flow_handler.hass = mock_hass_with_covers

        # Mock weather entity validation to pass, but return different values based on call
        def mock_states_get(entity_id):
            if entity_id == MOCK_WEATHER_ENTITY_ID:
                # Valid weather entity for weather validation
                mock_weather_state = MagicMock()
                mock_weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}
                return mock_weather_state
            else:
                # Valid cover entities
                mock_cover_state = MagicMock()
                mock_cover_state.attributes = {"supported_features": 15}
                return mock_cover_state

        mock_hass_with_covers.states.get.side_effect = mock_states_get

        # Create user input
        user_input = {
            "covers": [MOCK_COVER_ENTITY_ID],
            "weather_entity_id": MOCK_WEATHER_ENTITY_ID,
        }

        # Patch the async_create_entry method to raise a TypeError during validation
        with patch.object(flow_handler, "async_create_entry") as mock_create_entry:
            mock_create_entry.side_effect = TypeError("Test type error")

            # Execute config flow with input that triggers the exception
            result = await flow_handler.async_step_user(user_input)
            result_dict = cast(dict[str, Any], result)

            # Verify error handling returns to form with appropriate error message
            assert result_dict["type"] == FlowResultType.FORM
            assert result_dict["errors"]["base"] == ERROR_INVALID_CONFIG

    @pytest.mark.asyncio
    async def test_async_get_options_flow_static_method(self) -> None:
        """Test the static method async_get_options_flow.

        This test covers line 125 in config_flow.py by calling the static method
        directly.
        """
        # Create a mock config entry
        mock_config_entry = MagicMock()
        mock_config_entry.data = {"covers": [MOCK_COVER_ENTITY_ID]}

        # Call the static method
        options_flow = FlowHandler.async_get_options_flow(mock_config_entry)

        # Verify that it returns an OptionsFlowHandler instance
        assert isinstance(options_flow, OptionsFlowHandler)
        assert options_flow.config_entry == mock_config_entry

    async def test_cover_name_lookup_with_hass_and_state(
        self,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test cover name lookup when hass and cover_state exist.

        This test covers lines 206-208 in config_flow.py by ensuring the hass
        object exists and the cover state is available for name lookup.
        """
        # Create an options flow with a mock config entry
        mock_config_entry = MagicMock()
        mock_config_entry.data = {"covers": [MOCK_COVER_ENTITY_ID]}

        options_flow = OptionsFlowHandler(mock_config_entry)
        options_flow.hass = mock_hass_with_covers

        # Mock cover state with a friendly name
        mock_cover_state = MagicMock()
        mock_cover_state.attributes = {"friendly_name": "Test Cover"}
        mock_hass_with_covers.states.get.return_value = mock_cover_state

        # Execute the initial options flow step which triggers cover name lookup
        result = await options_flow.async_step_init()
        result_dict = cast(dict[str, Any], result)

        # Verify the form is displayed successfully (name lookup succeeded)
        assert result_dict["type"] == FlowResultType.FORM
        assert "data_schema" in result_dict

        # Verify that the states.get was called for the cover entity
        mock_hass_with_covers.states.get.assert_called_with(MOCK_COVER_ENTITY_ID)

    async def test_cover_name_lookup_with_hass_but_no_state(
        self,
        mock_hass_with_covers: MagicMock,
    ) -> None:
        """Test cover name lookup when hass exists but cover_state is None.

        This test covers the alternative path in lines 206-208 where hass exists
        but the cover state is not available.
        """
        # Create an options flow with a mock config entry
        mock_config_entry = MagicMock()
        mock_config_entry.data = {"covers": [MOCK_COVER_ENTITY_ID]}

        options_flow = OptionsFlowHandler(mock_config_entry)
        options_flow.hass = mock_hass_with_covers

        # Mock that the cover state is not found (returns None)
        mock_hass_with_covers.states.get.return_value = None

        # Execute the initial options flow step
        result = await options_flow.async_step_init()
        result_dict = cast(dict[str, Any], result)

        # Verify the form is still displayed (graceful handling of missing state)
        assert result_dict["type"] == FlowResultType.FORM
        assert "data_schema" in result_dict

        # Verify that the states.get was called for the cover entity
        mock_hass_with_covers.states.get.assert_called_with(MOCK_COVER_ENTITY_ID)
