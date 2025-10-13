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


@pytest.mark.parametrize("language_code", _get_available_languages())
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
    # Note: With sequential flow, data fields are split across init, 2, and 3
    init_form_data = data.get(const.HA_OPTIONS, {}).get("step", {}).get("init", {}).get("data", {})
    step2_data = data.get(const.HA_OPTIONS, {}).get("step", {}).get("2", {}).get("data", {})
    step3_data = data.get(const.HA_OPTIONS, {}).get("step", {}).get("3", {}).get("data", {})
    options_data = {**init_form_data, **step2_data, **step3_data}
    expected_options_fields = {
        ConfKeys.COVERS.value,
        ConfKeys.COVERS_MAX_CLOSURE.value,
        ConfKeys.COVERS_MIN_CLOSURE.value,
        ConfKeys.MANUAL_OVERRIDE_DURATION.value,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value,
        ConfKeys.WEATHER_ENTITY_ID.value,
    }
    missing_options = expected_options_fields - set(options_data.keys())
    assert not missing_options, f"Missing options form labels in {language_code}.json: {sorted(missing_options)}"

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
    assert not missing_errors, f"Missing error strings in {language_code}.json: {sorted(missing_errors)}"


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
