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
    assert ConfKeys.TEMP_SENSOR_ENTITY_ID.value in schema
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
        ConfKeys.TEMP_SENSOR_ENTITY_ID.value: "sensor.living_room",
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


@pytest.mark.asyncio
async def test_options_flow_direction_field_defaults_and_parsing() -> None:
    """Direction fields should parse numeric strings/ints and omit default for invalid values."""
    data = {
        ConfKeys.COVERS.value: ["cover.one", "cover.two", "cover.three"],
        # Store raw values across data/options the way HA would
        "cover.one_cover_azimuth": "90",  # numeric string -> default 90
        "cover.two_cover_azimuth": 270,  # int -> default 270
        "cover.three_cover_azimuth": "west",  # invalid -> no default
    }

    # Put some values into options to ensure options take precedence
    options = {
        "cover.one_cover_azimuth": "180",  # overrides data to 180 default
    }

    flow = OptionsFlowHandler(_mock_entry(data, options))

    result = await flow.async_step_init()
    result_dict = cast(dict[str, Any], result)
    schema = result_dict["data_schema"].schema

    # Voluptuous stores defaults on the marker; ensure present for 1 and 2, not for 3
    assert "cover.one_cover_azimuth" in schema
    assert "cover.two_cover_azimuth" in schema
    assert "cover.three_cover_azimuth" in schema

    # Check defaults via the marker's default attribute, which may be a callable
    marker_one = next(k for k in schema.keys() if getattr(k, "schema", None) == "cover.one_cover_azimuth")
    marker_two = next(k for k in schema.keys() if getattr(k, "schema", None) == "cover.two_cover_azimuth")
    marker_three = next(k for k in schema.keys() if getattr(k, "schema", None) == "cover.three_cover_azimuth")

    def _resolve_default(marker: object) -> Any:
        if hasattr(marker, "default"):
            dv = getattr(marker, "default")
            return dv() if callable(dv) else dv
        return None

    assert _resolve_default(marker_one) == 180.0
    assert _resolve_default(marker_two) == 270.0
    # Invalid input should not yield a numeric default
    val3 = _resolve_default(marker_three)
    assert not isinstance(val3, (int, float))
