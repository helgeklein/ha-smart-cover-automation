"""Tests for the Smart Cover Automation config flow.

This module tests the initial configuration flow for setting up the integration.
The config flow simply shows a welcome message and creates an entry with empty data.
Users configure the integration via the options flow.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.data_entry_flow import FlowResultType

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config_flow import FlowHandler


def _as_dict(result: ConfigFlowResult) -> dict[str, Any]:
    """Convert ConfigFlowResult to dictionary for test assertions."""
    return cast(dict[str, Any], result)


class TestConfigFlow:
    """Test the simplified config flow (welcome screen only)."""

    async def test_step_user_shows_form_initially(self) -> None:
        """Test that step user shows the welcome form on initial call."""
        flow = FlowHandler()

        result = await flow.async_step_user(None)
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.FORM
        assert result_dict["step_id"] == "user"
        # Should have empty schema (no input fields)
        assert result_dict["data_schema"].schema == {}

    async def test_step_user_creates_entry_with_empty_data(self) -> None:
        """Test that submitting the form creates an entry with empty data."""
        flow = FlowHandler()

        # User submits the form (with empty input)
        result = await flow.async_step_user({})
        result_dict = _as_dict(result)

        assert result_dict["type"] == FlowResultType.CREATE_ENTRY
        assert result_dict["title"] == const.INTEGRATION_NAME
        assert result_dict["data"] == {}


class TestConfigFlowStaticMethod:
    """Test static methods of FlowHandler."""

    async def test_async_get_options_flow(self) -> None:
        """Test async_get_options_flow returns an OptionsFlowHandler."""
        from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler

        mock_entry = MagicMock()
        options_flow = FlowHandler.async_get_options_flow(mock_entry)

        assert isinstance(options_flow, OptionsFlowHandler)
        assert options_flow._config_entry == mock_entry
