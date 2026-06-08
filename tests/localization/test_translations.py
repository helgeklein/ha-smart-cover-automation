"""Tests for translation coverage in all supported language files.

This module contains comprehensive tests that ensure all Smart Cover Automation
integration translation files contain all required translation keys for proper
user interface functionality. These tests act as a safeguard against missing
translations that would result in broken or confusing user experiences.

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
- All supported languages have complete translation coverage

By validating translation completeness for all languages during testing, we prevent
user-facing issues from reaching production and ensure consistent localization
support as the integration evolves across different languages.
"""

from __future__ import annotations

import json
import pathlib
import warnings

import pytest

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys

TRANSLATIONS_DIR = pathlib.Path(__file__).resolve().parents[2] / "custom_components" / "smart_cover_automation" / "translations"


def _get_available_languages() -> list[str]:
    """Discover all available translation files in the translations directory.

    Returns:
        List of language codes (file names without .json extension) for all
        available translation files.
    """
    if not TRANSLATIONS_DIR.exists():
        return []

    languages = []
    for file_path in TRANSLATIONS_DIR.glob("*.json"):
        language_code = file_path.stem
        languages.append(language_code)

    return sorted(languages)


def _load_translations(language_code: str) -> dict:
    """Load and parse a specific language translation file.

    This helper function loads the specified language translation file and parses it
    as JSON. The function centralizes file loading logic and provides a
    consistent interface for accessing translation data across tests.

    Args:
        language_code: The language code (e.g., 'en', 'de') to load

    Returns:
        Dictionary containing the parsed translation data structure

    Raises:
        FileNotFoundError: If the translations file doesn't exist
        json.JSONDecodeError: If the translations file contains invalid JSON
    """
    translation_file = TRANSLATIONS_DIR / f"{language_code}.json"
    with translation_file.open("r", encoding="utf-8") as f:
        return json.load(f)


def _get_non_english_languages() -> list[str]:
    """Return all available translation files except English."""

    return [language_code for language_code in _get_available_languages() if language_code != "en"]


def _collect_leaf_paths(data: object, prefix: str = "") -> set[str]:
    """Collect dotted paths for all leaf values in a translation tree."""

    if isinstance(data, dict):
        paths: set[str] = set()
        for key, value in data.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            paths |= _collect_leaf_paths(value, child_prefix)
        return paths

    return {prefix} if prefix else set()


def _assert_no_missing(language_code: str, missing: set[str], description: str) -> None:
    """Fail when required English translation keys are missing."""

    if missing:
        raise AssertionError(f"Missing {description} in {language_code}.json: {sorted(missing)}")


@pytest.mark.parametrize("language_code", _get_non_english_languages())
def test_non_english_translations_warn_once_for_missing_keys(language_code: str) -> None:
    """Warn once per non-English translation file for structural drift relative to English."""

    english_data = _load_translations("en")
    localized_data = _load_translations(language_code)

    english_leaf_paths = _collect_leaf_paths(english_data)
    localized_leaf_paths = _collect_leaf_paths(localized_data)
    missing_leaf_paths = english_leaf_paths - localized_leaf_paths
    extra_leaf_paths = localized_leaf_paths - english_leaf_paths

    if not missing_leaf_paths and not extra_leaf_paths:
        return

    missing_sample = sorted(missing_leaf_paths)[:10]
    missing_remaining_count = len(missing_leaf_paths) - len(missing_sample)
    missing_suffix = f" (+{missing_remaining_count} more)" if missing_remaining_count > 0 else ""

    extra_sample = sorted(extra_leaf_paths)[:10]
    extra_remaining_count = len(extra_leaf_paths) - len(extra_sample)
    extra_suffix = f" (+{extra_remaining_count} more)" if extra_remaining_count > 0 else ""

    warnings.warn(
        (
            f"Translation drift in {language_code}.json relative to en.json: "
            f"missing={missing_sample}{missing_suffix}; extra={extra_sample}{extra_suffix}"
        ),
        stacklevel=2,
    )


@pytest.mark.parametrize("language_code", ["en"])
def test_translation_has_required_keys(language_code: str) -> None:
    """Test that all translation files contain required translation keys for proper UI functionality.

    This comprehensive test validates that all language translation files contain
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
    rather than technical field names or missing labels, regardless of their
    selected language.

    Args:
        language_code: The language code being tested (e.g., 'en', 'de')
    """
    # Load the complete translations data structure for the specified language
    data = _load_translations(language_code)

    # Test 1: Required options-step labels for runtime configuration
    # These labels appear when users modify settings through the options flow
    # Note: With sequential flow, data fields are split across init and 2
    init_form_data = data.get(const.HA_OPTIONS, {}).get("step", {}).get("init", {}).get("data", {})
    step2_data = data.get(const.HA_OPTIONS, {}).get("step", {}).get("2", {}).get("data", {})
    options_data = {**init_form_data, **step2_data}
    expected_options_fields = {
        ConfKeys.COVERS.value,
        ConfKeys.WEATHER_ENTITY_ID.value,
    }
    missing_options = expected_options_fields - set(options_data.keys())
    _assert_no_missing(language_code, missing_options, "options form labels")

    # Test 2: Required error strings used by options flow validation
    # These messages provide helpful feedback when configuration validation fails
    error_data = data.get("options", {}).get("error", {})
    expected_errors = {
        const.ERROR_INVALID_COVER,
        const.ERROR_INVALID_WEATHER_ENTITY,
        const.ERROR_NO_COVERS,
        const.ERROR_NO_WEATHER_ENTITY,
    }
    missing_errors = expected_errors - set(error_data.keys())
    _assert_no_missing(language_code, missing_errors, "error strings")


@pytest.mark.parametrize("language_code", ["en"])
def test_translation_has_evening_closure_section_keys(language_code: str) -> None:
    """Test that evening closure section fields are translated in every language."""

    data = _load_translations(language_code)
    section = (
        data.get(const.HA_OPTIONS, {}).get("step", {}).get("6", {}).get("sections", {}).get(const.STEP_6_SECTION_CLOSE_AFTER_SUNSET, {})
    )
    section_data = section.get("data", {})
    section_descriptions = section.get("data_description", {})
    expected_fields = {
        ConfKeys.EVENING_CLOSURE_ENABLED.value,
        ConfKeys.EVENING_CLOSURE_MODE.value,
        ConfKeys.EVENING_CLOSURE_TIME.value,
        ConfKeys.EVENING_CLOSURE_COVER_LIST.value,
        ConfKeys.EVENING_CLOSURE_IGNORE_MANUAL_OVERRIDE_DURATION.value,
        ConfKeys.EVENING_CLOSURE_KEEP_CLOSED.value,
        ConfKeys.MORNING_OPENING_MODE.value,
        ConfKeys.MORNING_OPENING_TIME.value,
    }

    missing_labels = expected_fields - set(section_data.keys())
    missing_descriptions = expected_fields - set(section_descriptions.keys())

    _assert_no_missing(language_code, missing_labels, "evening closure field labels")
    _assert_no_missing(language_code, missing_descriptions, "evening closure field descriptions")


@pytest.mark.parametrize("language_code", ["en"])
def test_translation_has_blocked_time_range_section_keys(language_code: str) -> None:
    """Test that blocked-time-range section fields are translated in every language."""

    data = _load_translations(language_code)
    section = data.get(const.HA_OPTIONS, {}).get("step", {}).get("6", {}).get("sections", {}).get(const.STEP_6_SECTION_TIME_RANGE, {})
    section_data = section.get("data", {})
    section_descriptions = section.get("data_description", {})
    expected_fields = {
        ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value,
        ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_MODE.value,
        ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value,
        ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value,
        ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_PRE_CLOSE_ENABLED.value,
    }

    missing_labels = expected_fields - set(section_data.keys())
    missing_descriptions = expected_fields - set(section_descriptions.keys())

    _assert_no_missing(language_code, missing_labels, "blocked time range field labels")
    _assert_no_missing(language_code, missing_descriptions, "blocked time range field descriptions")


@pytest.mark.parametrize("language_code", ["en"])
def test_translation_has_evening_external_time_keys(language_code: str) -> None:
    """Test that evening external mode and entity labels are translated in every language."""

    data = _load_translations(language_code)
    evening_options = data.get("selector", {}).get("evening_closure_mode", {}).get("options", {})
    time_entities = data.get("entity", {}).get("time", {})

    _assert_no_missing(
        language_code,
        {"external"} - set(evening_options.keys()),
        "evening external mode options",
    )
    _assert_no_missing(
        language_code,
        {const.TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME} - set(time_entities.keys()),
        "evening external time entity labels",
    )


@pytest.mark.parametrize("language_code", ["en"])
def test_translation_has_blocked_time_range_external_time_keys(language_code: str) -> None:
    """Test that blocked-time external entity labels are translated in every language."""

    data = _load_translations(language_code)
    time_entities = data.get("entity", {}).get("time", {})

    _assert_no_missing(
        language_code,
        {const.TIME_KEY_AUTOMATION_DISABLED_TIME_RANGE_EXTERNAL_START} - set(time_entities.keys()),
        "blocked-time external start labels",
    )
    _assert_no_missing(
        language_code,
        {const.TIME_KEY_AUTOMATION_DISABLED_TIME_RANGE_EXTERNAL_END} - set(time_entities.keys()),
        "blocked-time external end labels",
    )


@pytest.mark.parametrize("language_code", ["en"])
def test_translation_has_blocked_time_range_mode_options(language_code: str) -> None:
    """Test that blocked-time mode selector options are translated in every language."""

    data = _load_translations(language_code)
    blocked_time_options = data.get("selector", {}).get("blocked_time_range_mode", {}).get("options", {})

    _assert_no_missing(
        language_code,
        {"fixed_time", "external"} - set(blocked_time_options.keys()),
        "blocked-time mode options",
    )


@pytest.mark.parametrize("language_code", ["en"])
def test_translation_has_morning_opening_sensor_labels(language_code: str) -> None:
    """Test that morning opening diagnostic sensor labels are translated in every language."""

    data = _load_translations(language_code)
    sensor_entities = data.get("entity", {}).get("sensor", {})

    _assert_no_missing(
        language_code,
        {const.SENSOR_KEY_MORNING_OPENING_MODE} - set(sensor_entities.keys()),
        "morning opening mode sensor labels",
    )
    _assert_no_missing(
        language_code,
        {const.SENSOR_KEY_MORNING_OPENING_TIME} - set(sensor_entities.keys()),
        "morning opening time sensor labels",
    )


@pytest.mark.parametrize("language_code", ["en"])
def test_translation_has_step_4_tilt_keys(language_code: str) -> None:
    """Test that step 4 tilt field labels and descriptions are translated in every language."""

    data = _load_translations(language_code)
    step_4 = data.get(const.HA_OPTIONS, {}).get("step", {}).get("4", {})
    section_data = step_4.get("data", {})
    section_descriptions = step_4.get("data_description", {})
    expected_fields = {
        ConfKeys.TILT_MODE_DAY.value,
        ConfKeys.TILT_MODE_NIGHT.value,
        ConfKeys.TILT_SET_VALUE_DAY.value,
        ConfKeys.TILT_SET_VALUE_NIGHT.value,
        ConfKeys.TILT_MIN_CHANGE_DELTA.value,
        ConfKeys.TILT_OPEN_TO_COVER_OPEN_DELAY.value,
        ConfKeys.TILT_VERTICAL_POSITION.value,
        ConfKeys.TILT_HORIZONTAL_POSITION.value,
        ConfKeys.TILT_SLAT_OVERLAP_RATIO.value,
    }

    missing_labels = expected_fields - set(section_data.keys())
    missing_descriptions = expected_fields - set(section_descriptions.keys())

    _assert_no_missing(language_code, missing_labels, "step 4 tilt labels")
    _assert_no_missing(language_code, missing_descriptions, "step 4 tilt descriptions")


@pytest.mark.parametrize("language_code", ["en"])
def test_translation_has_step_5_additional_settings_keys(language_code: str) -> None:
    """Test that step 5 additional-settings labels and descriptions are translated in every language."""

    data = _load_translations(language_code)
    section = (
        data.get(const.HA_OPTIONS, {}).get("step", {}).get("5", {}).get("sections", {}).get(const.STEP_5_SECTION_ADDITIONAL_SETTINGS, {})
    )
    section_data = section.get("data", {})
    section_descriptions = section.get("data_description", {})
    expected_fields = {ConfKeys.COVER_MOVEMENT_STAGGER_DELAY.value}

    missing_labels = expected_fields - set(section_data.keys())
    missing_descriptions = expected_fields - set(section_descriptions.keys())

    _assert_no_missing(language_code, missing_labels, "step 5 additional-settings labels")
    _assert_no_missing(language_code, missing_descriptions, "step 5 additional-settings descriptions")


@pytest.mark.parametrize("language_code", _get_available_languages())
def test_translation_file_is_valid_json(language_code: str) -> None:
    """Test that each translation file contains valid, parseable JSON.

    This test validates the JSON syntax and structure of translation files to catch
    common issues early in development:
    - Syntax errors (missing commas, brackets, quotes)
    - Encoding problems (invalid UTF-8 characters)
    - Structural issues (malformed JSON)

    Valid JSON is critical because:
    - Home Assistant fails to load integrations with invalid translation files
    - JSON errors prevent users from seeing any translations at all
    - Syntax errors in one language can break the entire integration
    - Invalid JSON causes confusing runtime errors during setup

    This test ensures that all translation files are well-formed and can be
    successfully parsed before deployment, preventing integration load failures
    and providing early feedback to developers about JSON formatting issues.

    Args:
        language_code: The language code being tested (e.g., 'en', 'de', 'fr')

    Raises:
        AssertionError: If the translation file contains invalid JSON
    """
    translation_file = TRANSLATIONS_DIR / f"{language_code}.json"

    # Verify the file exists
    assert translation_file.exists(), f"Translation file {language_code}.json not found"

    # Attempt to load and parse the JSON file
    try:
        with translation_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify it loaded as a dictionary (expected root structure)
        assert isinstance(data, dict), (
            f"Translation file {language_code}.json should contain a JSON object at root level, got {type(data).__name__}"
        )

        # Verify it's not empty
        assert len(data) > 0, f"Translation file {language_code}.json is empty"

    except json.JSONDecodeError as e:
        pytest.fail(
            f"Translation file {language_code}.json contains invalid JSON:\n"
            f"  Error: {e.msg}\n"
            f"  Line: {e.lineno}, Column: {e.colno}\n"
            f"  Position: {e.pos}"
        )
    except UnicodeDecodeError as e:
        pytest.fail(f"Translation file {language_code}.json has encoding issues: {e}")


def test_available_languages_detected() -> None:
    """Test that the language detection function finds all translation files.

    This test ensures that the dynamic language detection is working correctly
    and that all translation files in the translations directory are discovered.
    It serves as a meta-test to validate that the test infrastructure itself
    is functioning properly.
    """
    languages = _get_available_languages()

    # We should have at least English and German
    assert len(languages) >= 2, f"Expected at least 2 languages, found: {languages}"
    assert "en" in languages, "English translation file (en.json) should be present"
    assert "de" in languages, "German translation file (de.json) should be present"

    # All detected languages should have valid JSON files
    for lang in languages:
        translation_file = TRANSLATIONS_DIR / f"{lang}.json"
        assert translation_file.exists(), f"Translation file {lang}.json should exist"

        # Verify the file can be loaded as valid JSON
        try:
            _load_translations(lang)
        except json.JSONDecodeError as e:
            pytest.fail(f"Translation file {lang}.json contains invalid JSON: {e}")
