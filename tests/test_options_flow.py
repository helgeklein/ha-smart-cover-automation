"""Tests for the Options Flow of Smart Cover Automation."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler
from custom_components.smart_cover_automation.const import (
    CONF_COVERS,
    CONF_ENABLED,
    CONF_MAX_CLOSURE,
    CONF_SUN_ELEVATION_THRESHOLD,
    CONF_TEMP_SENSOR,
    DEFAULT_SUN_ELEVATION_THRESHOLD,
)


def _mock_entry(
    data: dict[str, Any], options: dict[str, Any] | None = None
) -> MagicMock:
    entry = MagicMock()
    entry.data = data
    entry.options = options or {}
    return entry


@pytest.mark.asyncio
async def test_options_flow_form_shows_dynamic_fields() -> None:
    """Form should include global options and per-cover direction fields."""
    data = {
        CONF_COVERS: ["cover.one", "cover.two"],
        CONF_SUN_ELEVATION_THRESHOLD: DEFAULT_SUN_ELEVATION_THRESHOLD,
    }
    flow = OptionsFlowHandler(_mock_entry(data))

    result = await flow.async_step_init()
    assert result["type"] == "form"
    schema = result["data_schema"].schema

    # Global options exposed
    assert CONF_ENABLED in schema
    assert CONF_TEMP_SENSOR in schema
    assert CONF_SUN_ELEVATION_THRESHOLD in schema
    assert CONF_MAX_CLOSURE in schema

    # Dynamic per-cover directions
    assert "cover.one_cover_direction" in schema
    assert "cover.two_cover_direction" in schema


@pytest.mark.asyncio
async def test_options_flow_submit_creates_entry() -> None:
    """Submitting options returns a CREATE_ENTRY with the data."""
    data = {CONF_COVERS: ["cover.one"]}
    flow = OptionsFlowHandler(_mock_entry(data))

    user_input = {
        CONF_ENABLED: False,
        CONF_TEMP_SENSOR: "sensor.living_room",
        CONF_SUN_ELEVATION_THRESHOLD: 30,
        CONF_MAX_CLOSURE: 75,
        "cover.one_cover_direction": "south",
    }

    result = await flow.async_step_init(user_input)
    assert result["type"] == "create_entry"
    assert result["title"] == "Options"
    assert result["data"] == user_input
