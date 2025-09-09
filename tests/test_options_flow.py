"""Tests for the Options Flow of Smart Cover Automation."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler
from custom_components.smart_cover_automation.settings import SETTINGS_SPECS, SettingsKey


def _mock_entry(data: dict[str, Any], options: dict[str, Any] | None = None) -> MagicMock:
    entry = MagicMock()
    entry.data = data
    entry.options = options or {}
    return entry


@pytest.mark.asyncio
async def test_options_flow_form_shows_dynamic_fields() -> None:
    """Form should include global options and per-cover direction fields."""
    data = {
        SettingsKey.COVERS.value: ["cover.one", "cover.two"],
        SettingsKey.SUN_ELEVATION_THRESHOLD.value: SETTINGS_SPECS[SettingsKey.SUN_ELEVATION_THRESHOLD].default,
    }
    flow = OptionsFlowHandler(_mock_entry(data))

    result = await flow.async_step_init()
    result_dict = cast(dict[str, Any], result)
    assert result_dict["type"] == "form"
    schema = result_dict["data_schema"].schema

    # Global options exposed
    assert SettingsKey.ENABLED.value in schema
    assert SettingsKey.TEMPERATURE_SENSOR.value in schema
    assert SettingsKey.SUN_ELEVATION_THRESHOLD.value in schema
    assert SettingsKey.MAX_CLOSURE.value in schema

    # Dynamic per-cover directions
    assert "cover.one_cover_direction" in schema
    assert "cover.two_cover_direction" in schema


@pytest.mark.asyncio
async def test_options_flow_submit_creates_entry() -> None:
    """Submitting options returns a CREATE_ENTRY with the data."""
    data = {SettingsKey.COVERS.value: ["cover.one"]}
    flow = OptionsFlowHandler(_mock_entry(data))

    user_input = {
        SettingsKey.ENABLED.value: False,
        SettingsKey.TEMPERATURE_SENSOR.value: "sensor.living_room",
        SettingsKey.SUN_ELEVATION_THRESHOLD.value: 30,
        SettingsKey.MAX_CLOSURE.value: 75,
        # Use numeric azimuth instead of legacy cardinal string
        "cover.one_cover_direction": 180,
    }

    result = await flow.async_step_init(user_input)
    result_dict = cast(dict[str, Any], result)
    assert result_dict["type"] == "create_entry"
    assert result_dict["title"] == "Options"
    assert result_dict["data"] == user_input
