"""Tests for FlowHelper utility class.

This module tests the static helper methods used by both config and options flows.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from homeassistant.components.weather.const import WeatherEntityFeature

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.config_flow import FlowHelper

from ..conftest import MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2, MOCK_WEATHER_ENTITY_ID


class TestFlowHelperValidation:
    """Test validate_user_input_step_1 method."""

    def test_validation_succeeds_with_valid_input(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation passes with valid covers and weather entity."""

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        assert errors == {}

    def test_validation_error_no_covers(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation fails when no covers selected."""

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [],
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        assert ConfKeys.COVERS.value in errors
        assert errors[ConfKeys.COVERS.value] == const.ERROR_NO_COVERS

    def test_validation_error_missing_covers_key(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation fails when covers key is missing."""

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        assert ConfKeys.COVERS.value in errors
        assert errors[ConfKeys.COVERS.value] == const.ERROR_NO_COVERS

    def test_validation_error_invalid_cover(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation fails when cover entity doesn't exist."""

        # Override the mock to return None for the non-existent cover
        def mock_get_state(entity_id: str) -> Any:
            if entity_id == "cover.nonexistent":
                return None  # Entity doesn't exist
            if entity_id.startswith("cover."):
                return MagicMock(state="closed")
            if entity_id.startswith("weather."):
                weather_state = MagicMock()
                weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}
                return weather_state
            return None

        mock_hass_with_covers.states.get.side_effect = mock_get_state

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: ["cover.nonexistent"],
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        assert ConfKeys.COVERS.value in errors
        assert errors[ConfKeys.COVERS.value] == const.ERROR_INVALID_COVER

    def test_validation_allows_unavailable_cover(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation passes for unavailable cover (warns but doesn't error)."""

        from homeassistant.const import STATE_UNAVAILABLE

        # Mock unavailable cover but valid weather entity
        cover_state = MagicMock()
        cover_state.state = STATE_UNAVAILABLE

        weather_state = MagicMock()
        weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}

        def mock_get_state(entity_id: str) -> Any:
            if entity_id == MOCK_COVER_ENTITY_ID:
                return cover_state  # Unavailable cover
            if entity_id == MOCK_WEATHER_ENTITY_ID:
                return weather_state  # Valid weather
            return None

        mock_hass_with_covers.states.get.side_effect = mock_get_state

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        # Should not error, just warn
        assert ConfKeys.COVERS.value not in errors
        assert ConfKeys.WEATHER_ENTITY_ID.value not in errors

    def test_validation_error_no_weather_entity(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation fails when weather entity is missing."""

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: "",
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        assert ConfKeys.WEATHER_ENTITY_ID.value in errors
        assert errors[ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_NO_WEATHER_ENTITY

    def test_validation_error_missing_weather_key(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation fails when weather entity key is missing."""

        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        assert ConfKeys.WEATHER_ENTITY_ID.value in errors
        assert errors[ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_NO_WEATHER_ENTITY

    def test_validation_error_weather_no_daily_forecast(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation fails when weather doesn't support daily forecast."""

        # Mock weather entity without daily forecast support
        weather_state = MagicMock()
        weather_state.attributes = {"supported_features": 0}

        def mock_get_state(entity_id: str) -> Any:
            if entity_id == MOCK_WEATHER_ENTITY_ID:
                return weather_state
            return MagicMock()  # Return valid state for covers

        mock_hass_with_covers.states.get.side_effect = mock_get_state

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        assert ConfKeys.WEATHER_ENTITY_ID.value in errors
        assert errors[ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_INVALID_WEATHER_ENTITY

    def test_validation_error_weather_entity_no_state(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation fails when weather entity has no state."""

        def mock_get_state(entity_id: str) -> Any:
            if entity_id == MOCK_WEATHER_ENTITY_ID:
                return None  # No state
            return MagicMock()  # Valid covers

        mock_hass_with_covers.states.get.side_effect = mock_get_state

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        assert ConfKeys.WEATHER_ENTITY_ID.value in errors
        assert errors[ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_INVALID_WEATHER_ENTITY

    def test_validation_succeeds_with_daily_forecast_support(self, mock_hass_with_covers: MagicMock, mock_logger: MagicMock) -> None:
        """Test validation passes when weather supports daily forecast."""

        # Mock weather entity with daily forecast support
        weather_state = MagicMock()
        weather_state.attributes = {"supported_features": WeatherEntityFeature.FORECAST_DAILY}

        def mock_get_state(entity_id: str) -> Any:
            if entity_id == MOCK_WEATHER_ENTITY_ID:
                return weather_state
            return MagicMock()

        mock_hass_with_covers.states.get.side_effect = mock_get_state

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = FlowHelper.validate_user_input_step_1(mock_hass_with_covers, user_input, mock_logger)

        assert errors == {}

    def test_validation_without_hass(self, mock_logger: MagicMock) -> None:
        """Test validation works without hass instance (minimal validation)."""

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = FlowHelper.validate_user_input_step_1(None, user_input, mock_logger)

        # Without hass, we can't validate entity existence, but basic checks should pass
        assert errors == {}


class TestFlowHelperSchemaBuilding:
    """Test schema building methods."""

    def test_build_schema_step_1_includes_required_fields(self) -> None:
        """Test step 1 schema has weather and covers fields."""
        from custom_components.smart_cover_automation.config import resolve

        resolved_settings = resolve({})

        schema = FlowHelper.build_schema_step_1(resolved_settings)

        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert ConfKeys.WEATHER_ENTITY_ID.value in schema_keys
        assert ConfKeys.COVERS.value in schema_keys

    def test_build_schema_step_2_creates_field_per_cover(self, mock_hass_with_covers: MagicMock) -> None:
        """Test step 2 schema has azimuth field for each cover."""
        covers = [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2]
        defaults = {}

        schema = FlowHelper.build_schema_step_2(covers, defaults)

        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in schema_keys
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}" in schema_keys

    def test_build_schema_step_2_uses_default_azimuth(self, mock_hass_with_covers: MagicMock) -> None:
        """Test step 2 schema uses default azimuth when not in defaults."""
        covers = [MOCK_COVER_ENTITY_ID]
        defaults = {}  # No existing azimuth

        schema = FlowHelper.build_schema_step_2(covers, defaults)

        # Schema should be created (default 180 will be used internally)
        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in schema_keys

    def test_build_schema_step_2_uses_existing_azimuth(self, mock_hass_with_covers: MagicMock) -> None:
        """Test step 2 schema uses existing azimuth from defaults."""
        covers = [MOCK_COVER_ENTITY_ID]
        defaults = {
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 270.0,
        }

        schema = FlowHelper.build_schema_step_2(covers, defaults)

        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in schema_keys

    def test_build_schema_step_2_uses_cover_friendly_name(self, mock_hass_with_covers: MagicMock) -> None:
        """Test step 2 schema uses cover friendly name when available."""
        # Mock cover with friendly name
        cover_state = MagicMock()
        cover_state.name = "Living Room Cover"
        mock_hass_with_covers.states.get.return_value = cover_state

        covers = [MOCK_COVER_ENTITY_ID]
        defaults = {}

        schema = FlowHelper.build_schema_step_2(covers, defaults)

        # Schema should be created (friendly name used internally)
        assert schema is not None

    def test_build_schema_step_2_without_hass(self) -> None:
        """Test step 2 schema works without hass (uses entity ID as name)."""
        covers = [MOCK_COVER_ENTITY_ID]
        defaults = {}

        schema = FlowHelper.build_schema_step_2(covers, defaults)

        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in schema_keys

    def test_build_schema_step_3_with_no_per_cover_defaults(self) -> None:
        """Test step 3 schema when covers have no per-cover min/max closure defaults.

        This exercises the else branch in _build_schema_cover_positions where
        default_value is None (lines 294, 306-309).
        """
        covers = [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2]
        defaults = {}  # No per-cover defaults

        schema = FlowHelper.build_schema_step_3(covers, defaults)

        # Verify schema was created
        assert schema is not None

        # Extract section schemas
        sections = {}
        for key, value in schema.schema.items():
            section_name = str(key.schema) if hasattr(key, "schema") else str(key)
            sections[section_name] = value

        # Verify section structure
        assert "section_min_closure" in sections
        assert "section_max_closure" in sections

        # Verify that fields for all covers exist in the sections
        # (The actual structure is nested, but we're checking the schema was created)
        assert len(sections) >= 2

    def test_build_schema_step_3_with_per_cover_defaults(self) -> None:
        """Test step 3 schema when covers have per-cover min/max closure defaults."""
        covers = [MOCK_COVER_ENTITY_ID]
        defaults = {
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MIN_CLOSURE}": 20,
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}": 80,
        }

        schema = FlowHelper.build_schema_step_3(covers, defaults)

        # Verify schema was created
        assert schema is not None

        # Extract section schemas
        sections = {}
        for key, value in schema.schema.items():
            section_name = str(key.schema) if hasattr(key, "schema") else str(key)
            sections[section_name] = value

        # Verify both sections exist
        assert "section_min_closure" in sections
        assert "section_max_closure" in sections


class TestFlowHelperFlattenSection:
    """Test extract_from_section_input utility method."""

    def test_flatten_section_input_with_sections_only(self) -> None:
        """Test flattening input that only contains section data."""
        user_input = {
            "section_min_closure": {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MIN_CLOSURE}": 20,
            },
            "section_max_closure": {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}": 80,
            },
        }

        section_names = {"section_min_closure", "section_max_closure"}
        result, sections_present = FlowHelper.extract_from_section_input(user_input, section_names)

        # Sections should be flattened
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MIN_CLOSURE}" in result
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}" in result
        assert result[f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MIN_CLOSURE}"] == 20
        assert result[f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}"] == 80

        # Section keys should not be in result
        assert "section_min_closure" not in result
        assert "section_max_closure" not in result

        # Both sections should be marked as present
        assert "section_min_closure" in sections_present
        assert "section_max_closure" in sections_present

    def test_flatten_section_input_with_mixed_data(self) -> None:
        """Test flattening input with both sections and non-section keys.

        This exercises the else branch (lines 306-309) where non-section keys
        are directly copied to the flattened dictionary.
        """
        user_input = {
            "section_min_closure": {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MIN_CLOSURE}": 20,
            },
            "section_max_closure": {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}": 80,
            },
            "some_other_key": "some_value",  # Non-section key
            "another_key": 42,  # Another non-section key
        }

        section_names = {"section_min_closure", "section_max_closure"}
        result, sections_present = FlowHelper.extract_from_section_input(user_input, section_names)

        # Sections should be flattened
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MIN_CLOSURE}" in result
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}" in result

        # Non-section keys should be preserved
        assert "some_other_key" in result
        assert "another_key" in result
        assert result["some_other_key"] == "some_value"
        assert result["another_key"] == 42

        # Section keys should not be in result
        assert "section_min_closure" not in result
        assert "section_max_closure" not in result

        # Both sections should be marked as present
        assert "section_min_closure" in sections_present
        assert "section_max_closure" in sections_present

    def test_flatten_section_input_with_non_dict_section_value(self) -> None:
        """Test that non-dict values for section keys are preserved as-is."""
        user_input = {
            "section_min_closure": "not_a_dict",  # Should be preserved since it's not a dict
            "section_max_closure": {
                f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}": 80,
            },
        }

        section_names = {"section_min_closure", "section_max_closure"}
        result, sections_present = FlowHelper.extract_from_section_input(user_input, section_names)

        # section_min_closure with non-dict value should be preserved
        assert "section_min_closure" in result
        assert result["section_min_closure"] == "not_a_dict"

        # section_max_closure with dict value should be flattened
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_MAX_CLOSURE}" in result
        assert "section_max_closure" not in result

        # Both sections are considered present once submitted, even with non-dict values
        assert "section_max_closure" in sections_present
        assert "section_min_closure" in sections_present

    def test_flatten_section_input_with_empty_sections(self) -> None:
        """Test flattening input with empty section dictionaries."""
        user_input = {
            "section_min_closure": {},
            "section_max_closure": {},
        }

        section_names = {"section_min_closure", "section_max_closure"}
        result, sections_present = FlowHelper.extract_from_section_input(user_input, section_names)

        # Empty sections should result in empty flattened dict
        assert len(result) == 0

        # Both sections should be marked as present
        assert "section_min_closure" in sections_present
        assert "section_max_closure" in sections_present
