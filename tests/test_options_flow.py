"""Tests for the Options Flow of Smart Cover Automation."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.config import CONF_SPECS, ConfKeys
from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler


def _mock_entry(data: dict[str, Any], options: dict[str, Any] | None = None) -> MagicMock:
    entry = MagicMock()
    entry.data = data
    entry.options = options or {}
    return entry


@pytest.mark.asyncio
async def test_options_flow_form_shows_dynamic_fields() -> None:
    """Form should include global options and per-cover direction fields."""
    data = {
        ConfKeys.COVERS.value: ["cover.one", "cover.two"],
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: CONF_SPECS[ConfKeys.SUN_ELEVATION_THRESHOLD].default,
    }
    flow = OptionsFlowHandler(_mock_entry(data))

    result = await flow.async_step_init()
    result_dict = cast(dict[str, Any], result)
    assert result_dict["type"] == "form"
    schema = result_dict["data_schema"].schema

    # Global options exposed
    assert ConfKeys.ENABLED.value in schema
    assert ConfKeys.TEMPERATURE_SENSOR.value in schema
    assert ConfKeys.SUN_ELEVATION_THRESHOLD.value in schema
    assert ConfKeys.MAX_CLOSURE.value in schema

    # Dynamic per-cover directions
    assert "cover.one_cover_azimuth" in schema
    assert "cover.two_cover_azimuth" in schema


@pytest.mark.asyncio
async def test_options_flow_submit_creates_entry() -> None:
    """Submitting options returns a CREATE_ENTRY with the data."""
    data = {ConfKeys.COVERS.value: ["cover.one"]}
    flow = OptionsFlowHandler(_mock_entry(data))

    user_input = {
        ConfKeys.ENABLED.value: False,
        ConfKeys.TEMPERATURE_SENSOR.value: "sensor.living_room",
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 30,
        ConfKeys.MAX_CLOSURE.value: 75,
        # Use numeric azimuth instead of legacy cardinal string
        "cover.one_cover_azimuth": 180,
    }

    result = await flow.async_step_init(user_input)
    result_dict = cast(dict[str, Any], result)
    assert result_dict["type"] == "create_entry"
    assert result_dict["title"] == "Options"
    assert result_dict["data"] == user_input
