"""Tests for dynamic external tilt number entities."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from custom_components.smart_cover_automation.const import (
    NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_DAY,
    NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_NIGHT,
    NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY,
    NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT,
)
from custom_components.smart_cover_automation.number import (
    CoverExternalTiltDayNumber,
    CoverExternalTiltNightNumber,
    GlobalExternalTiltDayNumber,
    GlobalExternalTiltNightNumber,
)


@pytest.mark.parametrize(
    ("entity_class", "config_key"),
    [
        (GlobalExternalTiltDayNumber, NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY),
        (GlobalExternalTiltNightNumber, NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT),
    ],
)
def test_global_external_tilt_number_native_value_is_none_when_unset(mock_coordinator_basic, entity_class, config_key) -> None:
    """Global external tilt numbers should report no value when unset."""

    entity = entity_class(mock_coordinator_basic)

    assert entity.native_value is None
    assert entity.unique_id == f"{mock_coordinator_basic.config_entry.entry_id}_{config_key}"


@pytest.mark.parametrize(
    ("entity_class", "config_key"),
    [
        (GlobalExternalTiltDayNumber, NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY),
        (GlobalExternalTiltNightNumber, NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT),
    ],
)
async def test_global_external_tilt_number_set_native_value_persists_integer(
    mock_coordinator_basic,
    entity_class,
    config_key,
) -> None:
    """Global external tilt numbers should persist integer values to options."""

    entity = entity_class(mock_coordinator_basic)
    mock_coordinator_basic.hass.config_entries.async_update_entry = Mock()

    await entity.async_set_native_value(37.0)

    mock_coordinator_basic.hass.config_entries.async_update_entry.assert_called_once()
    call_kwargs = mock_coordinator_basic.hass.config_entries.async_update_entry.call_args
    options = call_kwargs[1]["options"] if "options" in call_kwargs[1] else call_kwargs[0][1]
    assert options[config_key] == 37


@pytest.mark.parametrize(
    ("entity_class", "translation_key", "config_suffix"),
    [
        (
            CoverExternalTiltDayNumber,
            NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_DAY,
            "cover_tilt_external_value_day",
        ),
        (
            CoverExternalTiltNightNumber,
            NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_NIGHT,
            "cover_tilt_external_value_night",
        ),
    ],
)
def test_cover_external_tilt_number_translation_and_unique_id(
    mock_coordinator_basic,
    entity_class,
    translation_key,
    config_suffix,
) -> None:
    """Per-cover external tilt numbers should expose placeholders and unique IDs."""

    entity = entity_class(mock_coordinator_basic, "cover.test_cover")

    assert entity.entity_description.translation_key == translation_key
    assert entity.translation_placeholders == {"cover_name": "Test Cover"}
    assert entity.unique_id == f"{mock_coordinator_basic.config_entry.entry_id}_cover.test_cover_{config_suffix}"
