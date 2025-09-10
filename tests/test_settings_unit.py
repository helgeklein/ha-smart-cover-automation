from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.smart_cover_automation.config import (
    CONF_SPECS,
    ConfKeys,
    ResolvedConfig,
    resolve,
    resolve_entry,
)


def test_keys_and_defaults_registry_complete():
    # CONF_SPECS contains all enum members and mirrors string view
    assert set(CONF_SPECS.keys()) == set(ConfKeys)
    assert all(isinstance(key.value, str) for key in CONF_SPECS.keys())


def test_list_covers_normalized_via_resolve():
    # covers provided as a list should be normalized to a tuple by resolve()
    options = {ConfKeys.COVERS.value: ["cover.a", "cover.b"]}
    rs = resolve(options, data=None)
    assert isinstance(rs.covers, tuple)
    assert rs.covers == ("cover.a", "cover.b")


def test_resolve_priority_and_coercion_with_defaults_fallback():
    # options take priority over data
    data = {
        ConfKeys.MAX_TEMPERATURE.value: "18.5",  # will coerce to float 18.5 if chosen
        ConfKeys.ENABLED.value: 0,  # bool(0) -> False
    }
    options = {
        ConfKeys.MAX_TEMPERATURE.value: "20.0",  # chosen over data
        ConfKeys.MIN_POSITION_DELTA.value: "not-an-int",  # coercion fails -> default 5
    }

    rs: ResolvedConfig = resolve(options, data)

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
    rs = resolve({ConfKeys.COVERS.value: covers_input}, {})
    assert rs.covers == expected


def test_resolve_covers_string_and_non_iterable_behaviors():
    # String input is treated as an iterable of characters (back-compat behavior)
    rs = resolve({ConfKeys.COVERS.value: "cover.window"}, {})
    assert rs.covers == tuple("cover.window")

    # Non-iterable input results in an empty tuple via safe fallback
    class NotIterable:
        pass

    rs2 = resolve({ConfKeys.COVERS.value: NotIterable()}, {})
    assert rs2.covers == ()


def test_resolved_settings_accessors():
    rs = resolve(
        {
            ConfKeys.ENABLED.value: True,
            ConfKeys.MAX_TEMPERATURE.value: 30,
        },
        {},
    )

    # get() reads by enum; as_enum_dict returns mapping by enum
    assert rs.get(ConfKeys.MAX_TEMPERATURE) == 30.0
    enum_dict = rs.as_enum_dict()
    assert set(enum_dict.keys()) == set(ConfKeys)
    assert enum_dict[ConfKeys.ENABLED] is True


def test_resolve_entry_reads_from_attributes():
    entry = SimpleNamespace(options={ConfKeys.ENABLED.value: False}, data={ConfKeys.MAX_TEMPERATURE.value: 22})
    rs = resolve_entry(entry)
    assert rs.enabled is False
    assert rs.max_temperature == 22.0


def test_enum_members_values_are_canonical():
    # Ensure enum values match expected string keys used in config
    assert ConfKeys.ENABLED.value == "enabled"
    assert ConfKeys.MAX_TEMPERATURE.value == "max_temperature"
