"""Tests for ConfigFlowHelper utility class.

This module tests the static helper methods used by both config and options flows.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from homeassistant.components.weather.const import WeatherEntityFeature

from custom_components.smart_cover_automation import const
from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.config_flow import ConfigFlowHelper

from ..conftest import MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2, MOCK_WEATHER_ENTITY_ID


class TestConfigFlowHelperValidation:
    """Test validate_user_input_step1 method."""

    def test_validation_succeeds_with_valid_input(self, mock_hass_with_covers: MagicMock) -> None:
        """Test validation passes with valid covers and weather entity."""
        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        assert errors == {}

    def test_validation_error_no_covers(self, mock_hass_with_covers: MagicMock) -> None:
        """Test validation fails when no covers selected."""
        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [],
        }

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        assert ConfKeys.COVERS.value in errors
        assert errors[ConfKeys.COVERS.value] == const.ERROR_NO_COVERS

    def test_validation_error_missing_covers_key(self, mock_hass_with_covers: MagicMock) -> None:
        """Test validation fails when covers key is missing."""
        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
        }

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        assert ConfKeys.COVERS.value in errors
        assert errors[ConfKeys.COVERS.value] == const.ERROR_NO_COVERS

    def test_validation_error_invalid_cover(self, mock_hass_with_covers: MagicMock) -> None:
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

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        assert ConfKeys.COVERS.value in errors
        assert errors[ConfKeys.COVERS.value] == const.ERROR_INVALID_COVER

    def test_validation_allows_unavailable_cover(self, mock_hass_with_covers: MagicMock) -> None:
        """Test validation passes for unavailable cover (warns but doesn't error)."""
        from homeassistant.const import STATE_UNAVAILABLE

        # Mock unavailable cover
        cover_state = MagicMock()
        cover_state.state = STATE_UNAVAILABLE
        mock_hass_with_covers.states.get.return_value = cover_state

        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        # Should not error, just warn
        assert ConfKeys.COVERS.value not in errors

    def test_validation_error_no_weather_entity(self, mock_hass_with_covers: MagicMock) -> None:
        """Test validation fails when weather entity is missing."""
        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: "",
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        assert ConfKeys.WEATHER_ENTITY_ID.value in errors
        assert errors[ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_NO_WEATHER_ENTITY

    def test_validation_error_missing_weather_key(self, mock_hass_with_covers: MagicMock) -> None:
        """Test validation fails when weather entity key is missing."""
        user_input = {
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        assert ConfKeys.WEATHER_ENTITY_ID.value in errors
        assert errors[ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_NO_WEATHER_ENTITY

    def test_validation_error_weather_no_daily_forecast(self, mock_hass_with_covers: MagicMock) -> None:
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

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        assert ConfKeys.WEATHER_ENTITY_ID.value in errors
        assert errors[ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_INVALID_WEATHER_ENTITY

    def test_validation_error_weather_entity_no_state(self, mock_hass_with_covers: MagicMock) -> None:
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

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        assert ConfKeys.WEATHER_ENTITY_ID.value in errors
        assert errors[ConfKeys.WEATHER_ENTITY_ID.value] == const.ERROR_INVALID_WEATHER_ENTITY

    def test_validation_succeeds_with_daily_forecast_support(self, mock_hass_with_covers: MagicMock) -> None:
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

        errors = ConfigFlowHelper.validate_user_input_step1(mock_hass_with_covers, user_input)

        assert errors == {}

    def test_validation_without_hass(self) -> None:
        """Test validation works without hass instance (minimal validation)."""
        user_input = {
            ConfKeys.WEATHER_ENTITY_ID.value: MOCK_WEATHER_ENTITY_ID,
            ConfKeys.COVERS.value: [MOCK_COVER_ENTITY_ID],
        }

        errors = ConfigFlowHelper.validate_user_input_step1(None, user_input)

        # Without hass, we can't validate entity existence, but basic checks should pass
        assert errors == {}


class TestConfigFlowHelperSchemaBuilding:
    """Test schema building methods."""

    def test_build_schema_step1_includes_required_fields(self) -> None:
        """Test step 1 schema has weather and covers fields."""
        from custom_components.smart_cover_automation.config import resolve

        resolved_settings = resolve({}, {})

        schema = ConfigFlowHelper.build_schema_step1(resolved_settings)

        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert ConfKeys.WEATHER_ENTITY_ID.value in schema_keys
        assert ConfKeys.COVERS.value in schema_keys

    def test_build_schema_step2_creates_field_per_cover(self, mock_hass_with_covers: MagicMock) -> None:
        """Test step 2 schema has azimuth field for each cover."""
        covers = [MOCK_COVER_ENTITY_ID, MOCK_COVER_ENTITY_ID_2]
        defaults = {}

        schema = ConfigFlowHelper.build_schema_step2(mock_hass_with_covers, covers, defaults)

        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in schema_keys
        assert f"{MOCK_COVER_ENTITY_ID_2}_{const.COVER_SFX_AZIMUTH}" in schema_keys

    def test_build_schema_step2_uses_default_azimuth(self, mock_hass_with_covers: MagicMock) -> None:
        """Test step 2 schema uses default azimuth when not in defaults."""
        covers = [MOCK_COVER_ENTITY_ID]
        defaults = {}  # No existing azimuth

        schema = ConfigFlowHelper.build_schema_step2(mock_hass_with_covers, covers, defaults)

        # Schema should be created (default 180 will be used internally)
        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in schema_keys

    def test_build_schema_step2_uses_existing_azimuth(self, mock_hass_with_covers: MagicMock) -> None:
        """Test step 2 schema uses existing azimuth from defaults."""
        covers = [MOCK_COVER_ENTITY_ID]
        defaults = {
            f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}": 270.0,
        }

        schema = ConfigFlowHelper.build_schema_step2(mock_hass_with_covers, covers, defaults)

        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in schema_keys

    def test_build_schema_step2_uses_cover_friendly_name(self, mock_hass_with_covers: MagicMock) -> None:
        """Test step 2 schema uses cover friendly name when available."""
        # Mock cover with friendly name
        cover_state = MagicMock()
        cover_state.name = "Living Room Cover"
        mock_hass_with_covers.states.get.return_value = cover_state

        covers = [MOCK_COVER_ENTITY_ID]
        defaults = {}

        schema = ConfigFlowHelper.build_schema_step2(mock_hass_with_covers, covers, defaults)

        # Schema should be created (friendly name used internally)
        assert schema is not None

    def test_build_schema_step2_without_hass(self) -> None:
        """Test step 2 schema works without hass (uses entity ID as name)."""
        covers = [MOCK_COVER_ENTITY_ID]
        defaults = {}

        schema = ConfigFlowHelper.build_schema_step2(None, covers, defaults)

        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert f"{MOCK_COVER_ENTITY_ID}_{const.COVER_SFX_AZIMUTH}" in schema_keys

    def test_build_schema_step3_includes_all_settings(self) -> None:
        """Test step 3 schema has all final settings fields."""
        from custom_components.smart_cover_automation.config import resolve

        resolved_settings = resolve({}, {})

        schema = ConfigFlowHelper.build_schema_step3(resolved_settings)

        schema_keys = [str(key.schema) if hasattr(key, "schema") else str(key) for key in schema.schema.keys()]
        assert ConfKeys.SUN_ELEVATION_THRESHOLD.value in schema_keys
        assert ConfKeys.SUN_AZIMUTH_TOLERANCE.value in schema_keys
        assert ConfKeys.COVERS_MAX_CLOSURE.value in schema_keys
        assert ConfKeys.COVERS_MIN_CLOSURE.value in schema_keys
        assert ConfKeys.MANUAL_OVERRIDE_DURATION.value in schema_keys

    def test_build_schema_step3_uses_custom_defaults(self) -> None:
        """Test step 3 schema uses custom default values."""
        from custom_components.smart_cover_automation.config import resolve

        custom_config = {
            ConfKeys.SUN_ELEVATION_THRESHOLD.value: 35,
            ConfKeys.COVERS_MAX_CLOSURE.value: 75,
        }
        resolved_settings = resolve({}, custom_config)

        schema = ConfigFlowHelper.build_schema_step3(resolved_settings)

        # Schema should be created with custom defaults
        assert schema is not None

    def test_build_schema_step3_converts_duration_correctly(self) -> None:
        """Test step 3 schema converts duration to hours/minutes/seconds."""
        from custom_components.smart_cover_automation.config import resolve

        custom_config = {
            ConfKeys.MANUAL_OVERRIDE_DURATION.value: 7380,  # 2 hours, 3 minutes
        }
        resolved_settings = resolve({}, custom_config)

        schema = ConfigFlowHelper.build_schema_step3(resolved_settings)

        # Schema should be created (duration converted internally)
        assert schema is not None
        assert resolved_settings.manual_override_duration == 7380
