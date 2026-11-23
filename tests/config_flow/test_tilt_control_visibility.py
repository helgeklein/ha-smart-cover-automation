"""Tests for the conditional visibility of the step-5 tilt settings.

The tilt angle control select decides which tilt settings are shown: the day settings for
"day only" and "day and night", the night settings for "night only" and "day and night",
and the remaining tilt settings for every value except "off". Hidden fields are dropped
from the submitted input by Home Assistant and must keep their stored values.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.field_visibility import ConditionOperator

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys, resolve
from custom_components.smart_cover_automation.config_flow import FlowHelper
from custom_components.smart_cover_automation.const import TiltControl

from .test_config_flow_real_ha import (  # noqa: F401
    COVER_FEATURES,
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

# Feature bitmask of a cover with adjustable slats (gets per-cover tilt sections)
TILT_COVER_FEATURES = COVER_FEATURES | CoverEntityFeature.SET_TILT_POSITION

# Expected visibility conditions
TILT_DAY_VISIBLE = {
    "field": ConfKeys.TILT_CONTROL.value,
    "operator": ConditionOperator.IN,
    "value": [TiltControl.DAY_ONLY.value, TiltControl.DAY_AND_NIGHT.value],
}
TILT_NIGHT_VISIBLE = {
    "field": ConfKeys.TILT_CONTROL.value,
    "operator": ConditionOperator.IN,
    "value": [TiltControl.NIGHT_ONLY.value, TiltControl.DAY_AND_NIGHT.value],
}
TILT_ANY_VISIBLE = {
    "field": ConfKeys.TILT_CONTROL.value,
    "operator": ConditionOperator.IN,
    "value": [TiltControl.DAY_ONLY.value, TiltControl.NIGHT_ONLY.value, TiltControl.DAY_AND_NIGHT.value],
}


#
# _step_5_markers
#
def _step_5_markers(hass: HomeAssistant) -> dict[str, Any]:
    """Return the step-5 schema markers by field or section name."""

    schema = FlowHelper.build_schema_step_5_tilt(covers=[TEST_COVER_1], defaults={}, resolved_settings=resolve({}), hass=hass)
    return {str(marker): marker for marker in schema.schema}


#
# _open_step_5
#
async def _open_step_5(hass: HomeAssistant, extra_options: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Create an entry with a tilt-capable cover and walk the options flow up to the step-5 form.

    Returns:
        The config entry and the step-5 form result.
    """

    _register_cover_entity(hass, TEST_COVER_1, features=TILT_COVER_FEATURES)
    _register_weather_entity(hass)
    entry = _create_loaded_entry(hass, extra_options=extra_options)

    # Inputs for the steps before step 5; empty inputs keep the stored values
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
    while result["step_id"] != "5":
        result = _as_dict(await hass.config_entries.options.async_configure(result["flow_id"], step_inputs.get(result["step_id"], {})))
        assert result["type"] is FlowResultType.FORM

    return entry, result


#
# _submit_step_5_and_finish
#
async def _submit_step_5_and_finish(hass: HomeAssistant, flow_id: str, step_5_input: dict[str, Any]) -> None:
    """Submit step 5 with the given input and complete the remaining steps without changes."""

    result = _as_dict(await hass.config_entries.options.async_configure(flow_id, step_5_input))
    while result["type"] is FlowResultType.FORM:
        result = _as_dict(await hass.config_entries.options.async_configure(flow_id, {}))
    assert result["type"] is FlowResultType.CREATE_ENTRY


class TestTiltControlSchemaMarkers:
    """Schema-level checks: the step-5 markers carry the expected visible conditions."""

    #
    # test_tilt_control_is_always_visible
    #
    def test_tilt_control_is_always_visible(self, hass: HomeAssistant) -> None:
        """The tilt angle control select itself is not conditional."""

        assert getattr(_step_5_markers(hass)[ConfKeys.TILT_CONTROL.value], "visible", None) is None

    #
    # test_day_and_night_fields_depend_on_tilt_control
    #
    def test_day_and_night_fields_depend_on_tilt_control(self, hass: HomeAssistant) -> None:
        """Day and night settings are only shown for the matching tilt angle control values."""

        _register_cover_entity(hass, TEST_COVER_1, features=TILT_COVER_FEATURES)
        markers = _step_5_markers(hass)

        for key in (ConfKeys.TILT_MODE_DAY.value, ConfKeys.TILT_SET_VALUE_DAY.value, const.STEP_5_SECTION_TILT_DAY):
            assert markers[key].visible == TILT_DAY_VISIBLE, key
        for key in (ConfKeys.TILT_MODE_NIGHT.value, ConfKeys.TILT_SET_VALUE_NIGHT.value, const.STEP_5_SECTION_TILT_NIGHT):
            assert markers[key].visible == TILT_NIGHT_VISIBLE, key

    #
    # test_other_tilt_fields_are_hidden_when_off
    #
    def test_other_tilt_fields_are_hidden_when_off(self, hass: HomeAssistant) -> None:
        """The remaining tilt settings are shown for every tilt angle control value except off."""

        markers = _step_5_markers(hass)

        for key in (
            ConfKeys.TILT_MIN_CHANGE_DELTA,
            ConfKeys.TILT_DRIFT_TOLERANCE,
            ConfKeys.TILT_SLAT_OVERLAP_RATIO,
            ConfKeys.TILT_OPEN_TO_COVER_OPEN_DELAY,
            ConfKeys.COVER_MOVEMENT_TO_TILT_DELAY,
            ConfKeys.TILT_VERTICAL_POSITION,
            ConfKeys.TILT_HORIZONTAL_POSITION,
        ):
            assert markers[key.value].visible == TILT_ANY_VISIBLE, key.value


class TestTiltControlVisibilityRealHA:
    """Real HA flow manager: hidden tilt settings keep their stored values."""

    #
    # test_tilt_control_off_keeps_hidden_values
    #
    async def test_tilt_control_off_keeps_hidden_values(self, hass: HomeAssistant) -> None:
        """With tilt angle control off, submitted values of hidden fields are ignored and stored ones kept."""

        per_cover_day_key = f"{TEST_COVER_1}_{const.COVER_SFX_TILT_MODE_DAY}"
        stored = {
            ConfKeys.TILT_MODE_DAY.value: const.TiltMode.SET_VALUE.value,
            ConfKeys.TILT_SET_VALUE_DAY.value: 40,
            ConfKeys.TILT_MODE_NIGHT.value: const.TiltMode.OPEN.value,
            ConfKeys.TILT_MIN_CHANGE_DELTA.value: 7,
            per_cover_day_key: const.TiltMode.CLOSED.value,
        }
        entry, result = await _open_step_5(hass, extra_options=stored)

        await _submit_step_5_and_finish(
            hass,
            result["flow_id"],
            {
                ConfKeys.TILT_CONTROL.value: TiltControl.OFF.value,
                # Hidden fields: the frontend wouldn't send them; HA must drop them if sent anyway
                ConfKeys.TILT_MODE_DAY.value: const.TiltMode.AUTO.value,
                ConfKeys.TILT_SET_VALUE_DAY.value: 90,
                ConfKeys.TILT_MIN_CHANGE_DELTA.value: 20,
            },
        )

        assert entry.options[ConfKeys.TILT_CONTROL.value] == TiltControl.OFF
        for key, value in stored.items():
            assert entry.options[key] == value, key

    #
    # test_day_only_saves_day_fields_and_keeps_night_fields
    #
    async def test_day_only_saves_day_fields_and_keeps_night_fields(self, hass: HomeAssistant) -> None:
        """With "day only", the visible day settings are saved and the hidden night settings kept."""

        stored = {
            ConfKeys.TILT_MODE_NIGHT.value: const.TiltMode.OPEN.value,
            ConfKeys.TILT_SET_VALUE_NIGHT.value: 30,
        }
        entry, result = await _open_step_5(hass, extra_options=stored)

        await _submit_step_5_and_finish(
            hass,
            result["flow_id"],
            {
                ConfKeys.TILT_CONTROL.value: TiltControl.DAY_ONLY.value,
                ConfKeys.TILT_MODE_DAY.value: const.TiltMode.SET_VALUE.value,
                ConfKeys.TILT_SET_VALUE_DAY.value: 60,
                # Hidden field
                ConfKeys.TILT_MODE_NIGHT.value: const.TiltMode.CLOSED.value,
            },
        )

        assert entry.options[ConfKeys.TILT_CONTROL.value] == TiltControl.DAY_ONLY
        assert entry.options[ConfKeys.TILT_MODE_DAY.value] == const.TiltMode.SET_VALUE
        assert entry.options[ConfKeys.TILT_SET_VALUE_DAY.value] == 60
        for key, value in stored.items():
            assert entry.options[key] == value, key
