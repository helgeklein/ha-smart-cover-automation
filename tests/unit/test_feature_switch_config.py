"""Unit tests for the feature control configuration.

Evening closure, morning opening and tilt angle control are configured in the
configuration wizard and can also be changed at runtime by entities (evening
closure select, morning opening switch, tilt angle control select). These tests
cover their config specs.
"""

from __future__ import annotations

import pytest

from custom_components.smart_cover_automation.config import (
    CONF_SPECS,
    ConfKeys,
    is_runtime_configurable_key,
    resolve,
)
from custom_components.smart_cover_automation.const import EveningClosureControl, TiltControl


def test_morning_opening_defaults_to_on_and_is_runtime_configurable() -> None:
    """Morning opening defaults to on so existing installations keep their behavior."""

    assert CONF_SPECS[ConfKeys.MORNING_OPENING_ENABLED].default is True
    assert resolve({}).morning_opening_enabled is True
    # Changing it via the switch must only refresh the coordinator, not reload the integration
    assert is_runtime_configurable_key(ConfKeys.MORNING_OPENING_ENABLED.value)


def test_morning_opening_resolves_stored_off_value() -> None:
    """A stored False value resolves to off."""

    assert resolve({ConfKeys.MORNING_OPENING_ENABLED.value: False}).morning_opening_enabled is False


def test_evening_closure_is_runtime_configurable() -> None:
    """The evening closure select writes the setting, so it must not trigger a reload."""

    assert is_runtime_configurable_key(ConfKeys.EVENING_CLOSURE.value)


@pytest.mark.parametrize("value", list(EveningClosureControl), ids=lambda v: v.value)
def test_evening_closure_resolves_stored_value(value: EveningClosureControl) -> None:
    """Every evening closure option resolves from its stored string."""

    assert resolve({ConfKeys.EVENING_CLOSURE.value: value.value}).evening_closure == value


def test_evening_closure_invalid_value_falls_back_to_off() -> None:
    """An invalid stored evening closure value falls back to the default (off)."""

    assert resolve({ConfKeys.EVENING_CLOSURE.value: "invalid"}).evening_closure == EveningClosureControl.OFF


def test_tilt_control_defaults_to_day_and_night() -> None:
    """Tilt angle control defaults to day and night, i.e., the previous behavior."""

    assert resolve({}).tilt_control == TiltControl.DAY_AND_NIGHT
    assert is_runtime_configurable_key(ConfKeys.TILT_CONTROL.value)


@pytest.mark.parametrize("value", list(TiltControl), ids=lambda v: v.value)
def test_tilt_control_resolves_stored_value(value: TiltControl) -> None:
    """Every tilt control option resolves from its stored string."""

    assert resolve({ConfKeys.TILT_CONTROL.value: value.value}).tilt_control == value


def test_tilt_control_invalid_value_falls_back_to_default() -> None:
    """An invalid stored tilt control value falls back to the default."""

    assert resolve({ConfKeys.TILT_CONTROL.value: "invalid"}).tilt_control == TiltControl.DAY_AND_NIGHT
