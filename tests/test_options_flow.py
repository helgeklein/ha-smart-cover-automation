"""Tests for the Options Flow of Smart Cover Automation."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler
from custom_components.smart_cover_automation.settings import DEFAULTS, KEYS


def _mock_entry(data: dict[str, Any], options: dict[str, Any] | None = None) -> MagicMock:
    entry = MagicMock()
    entry.data = data
    entry.options = options or {}
    return entry


@pytest.mark.asyncio
async def test_options_flow_form_shows_dynamic_fields() -> None:
    """Form should include global options and per-cover direction fields."""
    data = {
        KEYS["COVERS"]: ["cover.one", "cover.two"],
        KEYS["SUN_ELEVATION_THRESHOLD"]: DEFAULTS["SUN_ELEVATION_THRESHOLD"],
    }
    flow = OptionsFlowHandler(_mock_entry(data))

    result = await flow.async_step_init()
    result_dict = cast(dict[str, Any], result)
    assert result_dict["type"] == "form"
    schema = result_dict["data_schema"].schema

    # Global options exposed
    assert KEYS["ENABLED"] in schema
    assert KEYS["TEMPERATURE_SENSOR"] in schema
    assert KEYS["SUN_ELEVATION_THRESHOLD"] in schema
    assert KEYS["MAX_CLOSURE"] in schema

    # Dynamic per-cover directions
    assert "cover.one_cover_direction" in schema
    assert "cover.two_cover_direction" in schema


@pytest.mark.asyncio
async def test_options_flow_submit_creates_entry() -> None:
    """Submitting options returns a CREATE_ENTRY with the data."""
    data = {KEYS["COVERS"]: ["cover.one"]}
    flow = OptionsFlowHandler(_mock_entry(data))

    user_input = {
        KEYS["ENABLED"]: False,
        KEYS["TEMPERATURE_SENSOR"]: "sensor.living_room",
        KEYS["SUN_ELEVATION_THRESHOLD"]: 30,
        KEYS["MAX_CLOSURE"]: 75,
        # Use numeric azimuth instead of legacy cardinal string
        "cover.one_cover_direction": 180,
    }

    result = await flow.async_step_init(user_input)
    result_dict = cast(dict[str, Any], result)
    assert result_dict["type"] == "create_entry"
    assert result_dict["title"] == "Options"
    assert result_dict["data"] == user_input
