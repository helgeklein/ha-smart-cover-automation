"""Tests for translation coverage in en.json.

Ensures that all keys referenced by forms and errors exist in the English
translations file. This guards against missing labels in the UI.
"""

from __future__ import annotations

import json
import pathlib

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys

TRANSLATIONS_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "smart_cover_automation" / "translations" / "en.json"
)


def _load_translations() -> dict:
    with TRANSLATIONS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_en_json_has_required_keys() -> None:
    data = _load_translations()

    # Required user-step labels
    user_data = data.get("config", {}).get("step", {}).get("user", {}).get("data", {})
    expected_user_fields = {
        ConfKeys.COVERS.value,
        ConfKeys.TEMP_THRESHOLD.value,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value,
    }
    missing_user = expected_user_fields - set(user_data.keys())
    assert not missing_user, f"Missing user form labels in en.json: {sorted(missing_user)}"

    # Required options-step labels
    options_data = data.get(const.HA_OPTIONS, {}).get("step", {}).get("init", {}).get("data", {})
    expected_options_fields = {
        ConfKeys.ENABLED.value,
        ConfKeys.VERBOSE_LOGGING.value,
        ConfKeys.COVERS.value,
        ConfKeys.TEMP_SENSOR_ENTITY_ID.value,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value,
        ConfKeys.COVERS_MAX_CLOSURE.value,
    }
    missing_options = expected_options_fields - set(options_data.keys())
    assert not missing_options, f"Missing options form labels in en.json: {sorted(missing_options)}"

    # Required error strings used by config flow
    error_data = data.get("config", {}).get("error", {})
    expected_errors = {
        const.ERROR_INVALID_COVER,
        const.ERROR_INVALID_CONFIG,
    }
    missing_errors = expected_errors - set(error_data.keys())
    assert not missing_errors, f"Missing error strings in en.json: {sorted(missing_errors)}"

    # Required abort reasons used by config flow
    abort_data = data.get("config", {}).get("abort", {})
    expected_abort = {const.ABORT_SINGLE_INSTANCE_ALLOWED}
    missing_abort = expected_abort - set(abort_data.keys())
    assert not missing_abort, f"Missing abort strings in en.json: {sorted(missing_abort)}"
