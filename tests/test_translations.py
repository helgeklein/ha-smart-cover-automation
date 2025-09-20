"""Tests for translation coverage in en.json.

This module contains comprehensive tests that ensure the Smart Cover Automation
integration's English translation file contains all required translation keys
for proper user interface functionality. These tests act as a safeguard against
missing translations that would result in broken or confusing user experiences.

Translation coverage areas tested:
1. **Config Flow Labels**: User-facing field labels for initial setup
2. **Options Flow Labels**: User-facing field labels for runtime configuration
3. **Error Messages**: User-friendly error descriptions for validation failures
4. **Abort Messages**: Clear explanations for setup process termination

The translation system is critical for user experience because:
- Missing labels result in technical field names being displayed to users
- Missing error messages provide no helpful feedback during configuration problems
- Missing abort messages leave users confused about why setup failed
- Inconsistent translations create a poor professional impression

These tests ensure that:
- All configuration form fields have proper human-readable labels
- All error conditions have helpful user-facing messages
- All abort conditions provide clear explanations to users
- The integration maintains professional UI standards

By validating translation completeness during testing, we prevent
user-facing issues from reaching production and ensure consistent
localization support as the integration evolves.
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
    """Load and parse the English translations file.

    This helper function loads the en.json translations file and parses it
    as JSON. The function centralizes file loading logic and provides a
    consistent interface for accessing translation data across tests.

    Returns:
        Dictionary containing the parsed translation data structure

    Raises:
        FileNotFoundError: If the translations file doesn't exist
        json.JSONDecodeError: If the translations file contains invalid JSON
    """
    with TRANSLATIONS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_en_json_has_required_keys() -> None:
    """Test that en.json contains all required translation keys for proper UI functionality.

    This comprehensive test validates that the English translations file contains
    all necessary keys for the integration's user interface. It checks four
    critical categories of translations that must be present for proper operation:

    1. **Config Flow User Step**: Labels for initial setup form fields
    2. **Options Flow Init Step**: Labels for runtime configuration form fields
    3. **Error Messages**: User-friendly descriptions for validation failures
    4. **Abort Messages**: Clear explanations for setup process termination

    The test uses set operations to identify missing keys and provides detailed
    error messages that help developers understand exactly which translations
    are missing and where they should be added.

    Test failure indicates that:
    - New configuration fields were added without corresponding translations
    - Error handling was implemented without user-friendly messages
    - Translation file structure was modified incorrectly
    - Required translation keys were accidentally removed

    This test ensures users always see professional, helpful text in the UI
    rather than technical field names or missing labels.
    """
    # Load the complete translations data structure
    data = _load_translations()

    # Test 1: Required user-step labels for initial configuration flow
    # These labels appear when users first set up the integration
    user_data = data.get("config", {}).get("step", {}).get("user", {}).get("data", {})
    expected_user_fields = {
        ConfKeys.COVERS.value,
        ConfKeys.TEMP_SENSOR_ENTITY_ID.value,
    }
    missing_user = expected_user_fields - set(user_data.keys())
    assert not missing_user, f"Missing user form labels in en.json: {sorted(missing_user)}"

    # Test 2: Required options-step labels for runtime configuration
    # These labels appear when users modify settings through the options flow
    options_data = data.get(const.HA_OPTIONS, {}).get("step", {}).get("init", {}).get("data", {})
    expected_options_fields = {
        ConfKeys.ENABLED.value,
        ConfKeys.SIMULATING.value,
        ConfKeys.VERBOSE_LOGGING.value,
        ConfKeys.COVERS.value,
        ConfKeys.TEMP_SENSOR_ENTITY_ID.value,
        ConfKeys.TEMP_THRESHOLD.value,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value,
        ConfKeys.COVERS_MAX_CLOSURE.value,
        const.COVER_AZIMUTH,
    }
    missing_options = expected_options_fields - set(options_data.keys())
    assert not missing_options, f"Missing options form labels in en.json: {sorted(missing_options)}"

    # Test 3: Required error strings used by config flow validation
    # These messages provide helpful feedback when configuration validation fails
    error_data = data.get("config", {}).get("error", {})
    expected_errors = {
        const.ERROR_INVALID_COVER,  # Invalid cover entity selection
        const.ERROR_INVALID_CONFIG,  # General configuration validation failure
    }
    missing_errors = expected_errors - set(error_data.keys())
    assert not missing_errors, f"Missing error strings in en.json: {sorted(missing_errors)}"

    # Test 4: Required abort reasons used by config flow termination
    # These messages explain why the setup process was terminated
    abort_data = data.get("config", {}).get("abort", {})
    expected_abort = {const.ABORT_SINGLE_INSTANCE_ALLOWED}  # Multiple instances not allowed
    missing_abort = expected_abort - set(abort_data.keys())
    assert not missing_abort, f"Missing abort strings in en.json: {sorted(missing_abort)}"
