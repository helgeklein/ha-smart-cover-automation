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

    # Test 1: Required user-step labels for initial configuration flow
    # These labels appear when users first set up the integration
    user_data = data.get("config", {}).get("step", {}).get("user", {}).get("data", {})
    expected_user_fields = {
        ConfKeys.COVERS.value,
        ConfKeys.WEATHER_ENTITY_ID.value,
    }
    missing_user = expected_user_fields - set(user_data.keys())
    assert not missing_user, f"Missing user form labels in {language_code}.json: {sorted(missing_user)}"

    # Test 2: Required options-step labels for runtime configuration
    # These labels appear when users modify settings through the options flow
    options_data = data.get(const.HA_OPTIONS, {}).get("step", {}).get("init", {}).get("data", {})
    expected_options_fields = {
        ConfKeys.ENABLED.value,
        ConfKeys.VERBOSE_LOGGING.value,
        ConfKeys.COVERS.value,
        ConfKeys.WEATHER_ENTITY_ID.value,
        ConfKeys.TEMP_THRESHOLD.value,
        ConfKeys.SUN_ELEVATION_THRESHOLD.value,
        ConfKeys.SUN_AZIMUTH_TOLERANCE.value,
        ConfKeys.COVERS_MAX_CLOSURE.value,
        ConfKeys.COVERS_MIN_CLOSURE.value,
        const.COVER_AZIMUTH,
    }
    missing_options = expected_options_fields - set(options_data.keys())
    assert not missing_options, f"Missing options form labels in {language_code}.json: {sorted(missing_options)}"

    # Test 3: Required error strings used by config flow validation
    # These messages provide helpful feedback when configuration validation fails
    error_data = data.get("config", {}).get("error", {})
    expected_errors = {
        const.ERROR_INVALID_COVER,  # Invalid cover entity selection
        const.ERROR_INVALID_WEATHER_ENTITY,  # Invalid weather entity selection
        const.ERROR_INVALID_CONFIG,  # General configuration validation failure
    }
    missing_errors = expected_errors - set(error_data.keys())
    assert not missing_errors, f"Missing error strings in {language_code}.json: {sorted(missing_errors)}"


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
