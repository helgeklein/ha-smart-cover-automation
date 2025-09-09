from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.smart_cover_automation.settings import (
    SETTINGS_SPECS,
    SETTINGS_SPECS_BY_STR,
    ResolvedSettings,
    SettingsKey,
    resolve,
    resolve_entry,
)


def test_keys_and_defaults_registry_complete():
    # SETTINGS_SPECS contains all enum members and mirrors string view
    assert set(SETTINGS_SPECS.keys()) == set(SettingsKey)
    for key in SettingsKey:
        assert SETTINGS_SPECS_BY_STR[key.value] is SETTINGS_SPECS[key]


def test_list_covers_normalized_via_resolve():
    # covers provided as a list should be normalized to a tuple by resolve()
    options = {"covers": ["cover.a", "cover.b"]}
    rs = resolve(options, data=None)
    assert isinstance(rs.covers, tuple)
    assert rs.covers == ("cover.a", "cover.b")


def test_resolve_priority_and_coercion_with_defaults_fallback():
    # options take priority over data
    data = {
        "max_temperature": "18.5",  # will coerce to float 18.5 if chosen
        "enabled": 0,  # bool(0) -> False
    }
    options = {
        "max_temperature": "20.0",  # chosen over data
        "min_position_delta": "not-an-int",  # coercion fails -> default 5
    }

    rs: ResolvedSettings = resolve(options, data)

    # Priority: options over data
    assert rs.max_temperature == 20.0

    # Coercion success from data for enabled (not overridden in options)
    assert rs.enabled is False

    # Coercion failure falls back to default and coerces that
    assert rs.min_position_delta == 5


@pytest.mark.parametrize(
    "covers_input,expected",
    [
        (None, ()),
        ([], ()),
        (("a", "b"), ("a", "b")),
        (["x", 123], ("x", "123")),
    ],
)
def test_resolve_covers_common_shapes(covers_input, expected):
    rs = resolve({"covers": covers_input}, {})
    assert rs.covers == expected


def test_resolve_covers_string_and_non_iterable_behaviors():
    # String input is treated as an iterable of characters (back-compat behavior)
    rs = resolve({"covers": "cover.window"}, {})
    assert rs.covers == tuple("cover.window")

    # Non-iterable input results in an empty tuple via safe fallback
    class NotIterable:
        pass

    rs2 = resolve({"covers": NotIterable()}, {})
    assert rs2.covers == ()


def test_resolved_settings_accessors():
    rs = resolve(
        {
            "enabled": True,
            "max_temperature": 30,
        },
        {},
    )

    # get() reads by enum; as_enum_dict returns mapping by enum
    assert rs.get(SettingsKey.MAX_TEMPERATURE) == 30.0
    enum_dict = rs.as_enum_dict()
    assert set(enum_dict.keys()) == set(SettingsKey)
    assert enum_dict[SettingsKey.ENABLED] is True


def test_resolve_entry_reads_from_attributes():
    entry = SimpleNamespace(options={"enabled": False}, data={"max_temperature": 22})
    rs = resolve_entry(entry)
    assert rs.enabled is False
    assert rs.max_temperature == 22.0


def test_enum_members_values_are_canonical():
    # Ensure enum values match expected string keys used in config
    assert SettingsKey.ENABLED.value == "enabled"
    assert SettingsKey.MAX_TEMPERATURE.value == "max_temperature"
