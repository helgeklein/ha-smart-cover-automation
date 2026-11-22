"""Tests for the conditional visibility of the evening closure / morning opening time limits.

The earliest/latest time limits only apply to the sun-relative modes. Since HA 2026.11, the
options flow shows them only when such a mode is selected (``visible`` conditions), and the
time fields only while their limit is switched on.

Covered here:
- the schema markers carry the expected ``visible`` conditions,
- real HA strips hidden fields from the submitted input, so stored values are kept,
- the HTTP API used by the frontend serializes the conditions.
"""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant import data_entry_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.field_visibility import ConditionOperator
from homeassistant.setup import async_setup_component

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys, resolve
from custom_components.smart_cover_automation.config_flow import FlowHelper

# Reuse the real-HA module's autouse fixtures (sun setup, logbook mock, lingering timers)
from .test_config_flow_real_ha import (  # noqa: F401
    TEST_COVER_1,
    _as_dict,
    _create_loaded_entry,
    _register_cover_entity,
    _register_weather_entity,
    _step_2_azimuth_input,
    expected_lingering_tasks,
    expected_lingering_timers,
    setup_dependencies,
)

# Sun-relative modes in which the time limits are shown
EVENING_SUN_RELATIVE_MODES = [const.EveningClosureMode.BEFORE_SUNSET.value, const.EveningClosureMode.AFTER_SUNSET.value]
MORNING_SUN_RELATIVE_MODES = [const.MorningOpeningMode.BEFORE_SUNRISE.value, const.MorningOpeningMode.AFTER_SUNRISE.value]

# (mode key, sun-relative modes, limit switch key, limit time key)
TIME_LIMITS = [
    (
        ConfKeys.EVENING_CLOSURE_MODE,
        EVENING_SUN_RELATIVE_MODES,
        ConfKeys.EVENING_CLOSURE_EARLIEST_ENABLED,
        ConfKeys.EVENING_CLOSURE_EARLIEST_TIME,
    ),
    (
        ConfKeys.EVENING_CLOSURE_MODE,
        EVENING_SUN_RELATIVE_MODES,
        ConfKeys.EVENING_CLOSURE_LATEST_ENABLED,
        ConfKeys.EVENING_CLOSURE_LATEST_TIME,
    ),
    (
        ConfKeys.MORNING_OPENING_MODE,
        MORNING_SUN_RELATIVE_MODES,
        ConfKeys.MORNING_OPENING_EARLIEST_ENABLED,
        ConfKeys.MORNING_OPENING_EARLIEST_TIME,
    ),
    (
        ConfKeys.MORNING_OPENING_MODE,
        MORNING_SUN_RELATIVE_MODES,
        ConfKeys.MORNING_OPENING_LATEST_ENABLED,
        ConfKeys.MORNING_OPENING_LATEST_TIME,
    ),
]


#
# _evening_section_markers
#
def _evening_section_markers() -> dict[str, Any]:
    """Return the step-7 evening closure section's schema markers by field name."""

    schema = FlowHelper.build_schema_step_7(covers=[TEST_COVER_1], resolved_settings=resolve({}))
    section_key = next(key for key in schema.schema if str(key) == const.STEP_7_SECTION_CLOSE_AFTER_SUNSET)
    section_schema = schema.schema[section_key].schema.schema
    return {marker.schema: marker for marker in section_schema}


#
# _open_step_7
#
async def _open_step_7(hass: HomeAssistant, extra_options: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
    """Create an entry and walk the options flow up to the step-7 form.

    Returns:
        The config entry and the step-7 form result.
    """

    _register_cover_entity(hass, TEST_COVER_1)
    _register_weather_entity(hass)
    entry = _create_loaded_entry(hass, extra_options=extra_options)

    # Inputs for the steps before step 7; empty inputs keep the stored values
    step_inputs: dict[str, dict[str, Any]] = {
        "init": {
            ConfKeys.WEATHER_ENTITY_ID.value: entry.options[ConfKeys.WEATHER_ENTITY_ID.value],
            ConfKeys.COVERS.value: [TEST_COVER_1],
        },
        "2": _step_2_azimuth_input({f"{TEST_COVER_1}_{const.COVER_SFX_AZIMUTH}": 180.0}),
        "3": {
            ConfKeys.DAYTIME_STRATEGY.value: "let_light_in",
            ConfKeys.DAYTIME_MOVEMENT_DIRECTIONS.value: "open_only",
        },
    }

    result = _as_dict(await hass.config_entries.options.async_init(entry.entry_id))
    while result["step_id"] != "7":
        result = _as_dict(await hass.config_entries.options.async_configure(result["flow_id"], step_inputs.get(result["step_id"], {})))
        assert result["type"] is FlowResultType.FORM

    return entry, result


#
# _submit_step_7
#
async def _submit_step_7(hass: HomeAssistant, flow_id: str, evening_section: dict[str, Any]) -> dict[str, Any]:
    """Submit the step-7 form with the given evening closure section input."""

    result = _as_dict(
        await hass.config_entries.options.async_configure(
            flow_id,
            {const.STEP_7_SECTION_CLOSE_AFTER_SUNSET: evening_section},
        )
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    return result


class TestTimeLimitSchemaMarkers:
    """The step-7 schema marks the time limit fields as conditionally visible."""

    #
    # test_time_limit_fields_have_visible_conditions
    #
    @pytest.mark.parametrize(("mode_key", "modes", "enabled_key", "time_key"), TIME_LIMITS)
    def test_time_limit_fields_have_visible_conditions(
        self,
        mode_key: ConfKeys,
        modes: list[str],
        enabled_key: ConfKeys,
        time_key: ConfKeys,
    ) -> None:
        """The switch depends on the mode; the time on the mode and the switch."""

        markers = _evening_section_markers()
        mode_condition = {"field": mode_key.value, "operator": ConditionOperator.IN, "value": modes}

        enabled_marker = markers[enabled_key.value]
        assert isinstance(enabled_marker, data_entry_flow.Required)
        assert enabled_marker.visible == mode_condition

        time_marker = markers[time_key.value]
        assert isinstance(time_marker, data_entry_flow.Required)
        assert time_marker.visible == [mode_condition, {"field": enabled_key.value, "value": True}]

    #
    # test_mode_fields_are_always_visible
    #
    def test_mode_fields_are_always_visible(self) -> None:
        """The mode selectors themselves are not conditional."""

        markers = _evening_section_markers()
        for key in (ConfKeys.EVENING_CLOSURE_MODE, ConfKeys.MORNING_OPENING_MODE):
            assert getattr(markers[key.value], "visible", None) is None


class TestTimeLimitVisibilityRealHA:
    """Real HA flow manager: hidden fields are dropped from the submitted input."""

    #
    # test_hidden_time_limits_keep_stored_values
    #
    async def test_hidden_time_limits_keep_stored_values(self, hass: HomeAssistant) -> None:
        """In the fixed-time modes, submitted time limit values are ignored and stored ones kept."""

        stored = {
            ConfKeys.EVENING_CLOSURE_EARLIEST_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_EARLIEST_TIME.value: "18:30:00",
            ConfKeys.MORNING_OPENING_LATEST_ENABLED.value: True,
            ConfKeys.MORNING_OPENING_LATEST_TIME.value: "07:15:00",
        }
        entry, result = await _open_step_7(hass, extra_options=stored)

        await _submit_step_7(
            hass,
            result["flow_id"],
            {
                ConfKeys.EVENING_CLOSURE_MODE.value: const.EveningClosureMode.FIXED_TIME.value,
                ConfKeys.MORNING_OPENING_MODE.value: const.MorningOpeningMode.FIXED_TIME.value,
                # Hidden fields: the frontend wouldn't send them; HA must drop them if sent anyway
                ConfKeys.EVENING_CLOSURE_EARLIEST_ENABLED.value: False,
                ConfKeys.EVENING_CLOSURE_EARLIEST_TIME.value: "17:00:00",
                ConfKeys.MORNING_OPENING_LATEST_ENABLED.value: False,
                ConfKeys.MORNING_OPENING_LATEST_TIME.value: "09:00:00",
            },
        )

        for key, value in stored.items():
            assert entry.options[key] == value

    #
    # test_hidden_time_field_keeps_stored_value_when_limit_is_off
    #
    async def test_hidden_time_field_keeps_stored_value_when_limit_is_off(self, hass: HomeAssistant) -> None:
        """Switching a limit off hides its time field, which then keeps its stored value."""

        stored = {
            ConfKeys.EVENING_CLOSURE_LATEST_ENABLED.value: True,
            ConfKeys.EVENING_CLOSURE_LATEST_TIME.value: "21:30:00",
        }
        entry, result = await _open_step_7(hass, extra_options=stored)

        await _submit_step_7(
            hass,
            result["flow_id"],
            {
                ConfKeys.EVENING_CLOSURE_MODE.value: const.EveningClosureMode.AFTER_SUNSET.value,
                ConfKeys.EVENING_CLOSURE_LATEST_ENABLED.value: False,
                ConfKeys.EVENING_CLOSURE_LATEST_TIME.value: "20:00:00",
            },
        )

        assert entry.options[ConfKeys.EVENING_CLOSURE_LATEST_ENABLED.value] is False
        assert entry.options[ConfKeys.EVENING_CLOSURE_LATEST_TIME.value] == "21:30:00"

    #
    # test_visible_time_limits_are_saved
    #
    async def test_visible_time_limits_are_saved(self, hass: HomeAssistant) -> None:
        """In the sun-relative modes, time limits are saved normally."""

        entry, result = await _open_step_7(hass)

        await _submit_step_7(
            hass,
            result["flow_id"],
            {
                ConfKeys.EVENING_CLOSURE_MODE.value: const.EveningClosureMode.AFTER_SUNSET.value,
                ConfKeys.EVENING_CLOSURE_EARLIEST_ENABLED.value: True,
                ConfKeys.EVENING_CLOSURE_EARLIEST_TIME.value: "18:30:00",
                ConfKeys.MORNING_OPENING_MODE.value: const.MorningOpeningMode.BEFORE_SUNRISE.value,
                ConfKeys.MORNING_OPENING_LATEST_ENABLED.value: True,
                ConfKeys.MORNING_OPENING_LATEST_TIME.value: "07:15:00",
            },
        )

        assert entry.options[ConfKeys.EVENING_CLOSURE_EARLIEST_ENABLED.value] is True
        assert entry.options[ConfKeys.EVENING_CLOSURE_EARLIEST_TIME.value] == "18:30:00"
        assert entry.options[ConfKeys.MORNING_OPENING_LATEST_ENABLED.value] is True
        assert entry.options[ConfKeys.MORNING_OPENING_LATEST_TIME.value] == "07:15:00"


class TestTimeLimitVisibilityHttpApi:
    """The options flow HTTP API (used by the frontend) serializes the visible conditions."""

    #
    # test_step_7_form_serializes_visible_conditions
    #
    async def test_step_7_form_serializes_visible_conditions(self, hass: HomeAssistant, hass_client: Any) -> None:
        """The serialized step-7 form contains the conditions of all time limit fields."""

        assert await async_setup_component(hass, "config", {})
        _entry, result = await _open_step_7(hass)

        client = await hass_client()
        response = await client.get(f"/api/config/config_entries/options/flow/{result['flow_id']}")
        assert response.status == 200
        body = await response.json()
        assert body["step_id"] == "7"

        section = next(field for field in body["data_schema"] if field["name"] == const.STEP_7_SECTION_CLOSE_AFTER_SUNSET)
        fields = {field["name"]: field for field in section["schema"]}

        for mode_key, modes, enabled_key, time_key in TIME_LIMITS:
            mode_condition = {"field": mode_key.value, "operator": ConditionOperator.IN.value, "value": modes}
            assert fields[enabled_key.value]["visible"] == mode_condition
            assert fields[time_key.value]["visible"] == [mode_condition, {"field": enabled_key.value, "value": True}]

        assert "visible" not in fields[ConfKeys.EVENING_CLOSURE_MODE.value]
