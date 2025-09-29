"""Tests for the Options Flow of Smart Cover Automation.

This module tests the Home Assistant configuration options flow, which allows users
to modify integration settings after initial setup. The options flow provides a UI
for updating global automation parameters and per-cover directional settings.

Key testing areas:
- Dynamic form generation based on configured covers
- Global option validation (temperature sensors, thresholds, automation state)
- Per-cover azimuth direction field handling and validation
- Data persistence and schema validation
- Default value resolution for numeric vs string inputs
- Integration with Home Assistant's voluptuous schema system

The options flow is critical for user experience as it allows runtime configuration
changes without requiring integration reinstallation or YAML editing.
"""

from __future__ import annotations

from typing import Any, cast

from custom_components.smart_cover_automation.config import CONF_SPECS, ConfKeys
from custom_components.smart_cover_automation.config_flow import OptionsFlowHandler
from custom_components.smart_cover_automation.const import COVER_SFX_AZIMUTH

from .conftest import create_options_flow_mock_entry


async def test_options_flow_form_shows_dynamic_fields() -> None:
    """Test that the options form dynamically includes fields based on configured covers.

    This test verifies the core functionality of the options flow: generating a form
    that includes both global automation settings and per-cover configuration fields.
    The form should adapt to the number and names of covers configured during setup.

    Test scenario:
    - Configuration with 2 covers: "cover.one" and "cover.two"
    - Default sun elevation threshold from initial setup
    - Expected form includes global settings + 2 cover-specific azimuth fields

    This ensures users can modify settings for all their covers without needing to
    reconfigure the entire integration.
    """
    # Create a configuration with two covers and a default sun threshold
    data = {
        ConfKeys.COVERS.value: ["cover.one", "cover.two"],
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: CONF_SPECS[ConfKeys.SUN_ELEVATION_THRESHOLD].default,
    }
    flow = OptionsFlowHandler(create_options_flow_mock_entry(data))

    # Trigger form generation with no user input
    result = await flow.async_step_init()
    result_dict = cast(dict[str, Any], result)

    # Verify we get a form (not an error or redirect)
    assert result_dict["type"] == "form"
    schema = result_dict["data_schema"].schema

    # Verify global automation options are present
    # These affect the entire integration's behavior
    assert ConfKeys.ENABLED.value in schema
    assert ConfKeys.WEATHER_ENTITY_ID.value in schema
    assert ConfKeys.SUN_ELEVATION_THRESHOLD.value in schema
    assert ConfKeys.COVERS_MAX_CLOSURE.value in schema
    assert ConfKeys.COVERS_MIN_CLOSURE.value in schema

    # Verify dynamic per-cover direction fields are present
    # These allow individual cover azimuth configuration
    assert f"cover.one_{COVER_SFX_AZIMUTH}" in schema
    assert f"cover.two_{COVER_SFX_AZIMUTH}" in schema


async def test_options_flow_submit_creates_entry() -> None:
    """Test that submitting valid options creates a configuration entry.

    This test verifies the complete options flow cycle: form display, user input
    collection, validation, and final configuration storage. When users submit
    the options form, their settings should be saved and applied to the integration.

    Test scenario:
    - Single cover configuration
    - User modifies all available global settings
    - User sets numeric azimuth for the cover (180° = south-facing)
    - Expected result: CREATE_ENTRY with all user input preserved

    This ensures user preferences are correctly captured and will persist across
    Home Assistant restarts.
    """
    # Start with minimal configuration (one cover)
    data = {ConfKeys.COVERS.value: ["cover.one"]}
    flow = OptionsFlowHandler(create_options_flow_mock_entry(data))

    # Simulate user filling out the options form with new values
    user_input = {
        ConfKeys.ENABLED.value: False,  # Disable automation
        ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",  # Custom weather entity
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 30,  # Higher sun threshold (30° vs default 20°)
        ConfKeys.COVERS_MAX_CLOSURE.value: 25,  # Partial closure limit (25 vs. 0)
        ConfKeys.COVERS_MIN_CLOSURE.value: 75,  # Partial opening limit (75 vs 100)
        # Use numeric azimuth instead of legacy cardinal string
        f"cover.one_{COVER_SFX_AZIMUTH}": 180,  # South-facing window
    }

    # Submit the form with user input
    result = await flow.async_step_init(user_input)
    result_dict = cast(dict[str, Any], result)

    # Verify successful submission creates a config entry
    assert result_dict["type"] == "create_entry"
    assert result_dict["title"] == "Options"
    # All user input should be preserved exactly as submitted
    assert result_dict["data"] == user_input


async def test_options_flow_direction_field_defaults_and_parsing() -> None:
    """Test direction field default values and parsing across different configuration scenarios.

    This test verifies robust handling of azimuth direction configurations:
    1. Numeric string values are parsed and set as defaults (e.g., "90" → 90.0°)
    2. Integer values are preserved as defaults (e.g., 270 → 270.0°)
    3. Invalid string values don't receive numeric defaults (graceful degradation)
    4. Options take precedence over initial data when both are present

    Test scenarios:
    - cover.one: "90" in data, overridden by "180" in options → 180.0° default
    - cover.two: 270 integer in data → 270.0° default
    - cover.three: "west" invalid string → non-numeric default (graceful fallback)

    This ensures the voluptuous schema system correctly parses user input and
    maintains reasonable defaults for precise solar automation calculations.
    """
    # Setup multi-cover configuration with various azimuth data types
    data = {
        ConfKeys.COVERS.value: ["cover.one", "cover.two", "cover.three"],
        # Store raw values across data/options the way HA would
        f"cover.one_{COVER_SFX_AZIMUTH}": "90",  # numeric string → should parse to 90.0°
        f"cover.two_{COVER_SFX_AZIMUTH}": 270,  # integer → should preserve as 270.0°
        f"cover.three_{COVER_SFX_AZIMUTH}": "west",  # invalid string → should handle gracefully
    }

    # Put some values into options to ensure options take precedence over data
    options = {
        f"cover.one_{COVER_SFX_AZIMUTH}": "180",  # overrides data: "90" → "180" → 180.0° default
    }

    flow = OptionsFlowHandler(create_options_flow_mock_entry(data, options))

    # Generate the options form schema
    result = await flow.async_step_init()
    result_dict = cast(dict[str, Any], result)
    schema = result_dict["data_schema"].schema

    # Voluptuous stores defaults on the marker; ensure fields are present for all covers
    assert f"cover.one_{COVER_SFX_AZIMUTH}" in schema
    assert f"cover.two_{COVER_SFX_AZIMUTH}" in schema
    assert f"cover.three_{COVER_SFX_AZIMUTH}" in schema

    # Check defaults via the marker's default attribute, which may be a callable
    # Find the voluptuous Required markers for each cover's azimuth field
    marker_one = next(k for k in schema.keys() if getattr(k, "schema", None) == f"cover.one_{COVER_SFX_AZIMUTH}")
    marker_two = next(k for k in schema.keys() if getattr(k, "schema", None) == f"cover.two_{COVER_SFX_AZIMUTH}")
    marker_three = next(k for k in schema.keys() if getattr(k, "schema", None) == f"cover.three_{COVER_SFX_AZIMUTH}")

    def _resolve_default(marker: object) -> Any:
        """Helper to resolve voluptuous default values (handles both static and callable defaults)."""
        if hasattr(marker, "default"):
            dv = getattr(marker, "default")
            return dv() if callable(dv) else dv
        return None

    # Verify parsing behavior for each configuration scenario
    assert _resolve_default(marker_one) == 180.0  # Options override: "180" → 180.0°
    assert _resolve_default(marker_two) == 270.0  # Integer preserved: 270 → 270.0°
    # Invalid input should not yield a numeric default (graceful degradation)
    val3 = _resolve_default(marker_three)
    assert not isinstance(val3, (int, float))  # "west" → non-numeric fallback


async def test_options_flow_simulation_mode_default_and_submit() -> None:
    """Test simulation mode configuration in the options flow.

    This test verifies that simulation mode is properly included in the options form
    with correct default values and that user input for simulation mode is correctly
    processed and stored.

    Test scenarios:
    1. Default simulation mode state (False) appears in form
    2. User can enable simulation mode via options form
    3. Simulation mode setting is properly stored in config entry
    """
    # Start with basic configuration
    data = {ConfKeys.COVERS.value: ["cover.living_room"]}
    flow = OptionsFlowHandler(create_options_flow_mock_entry(data))

    # First, check that simulation mode appears in the form with correct default
    result = await flow.async_step_init()
    result_dict = cast(dict[str, Any], result)
    schema = result_dict["data_schema"].schema

    # Verify simulation mode field is present
    simulation_key = ConfKeys.SIMULATING.value
    assert simulation_key in schema

    # Find the voluptuous marker and check default value
    simulation_marker = next(k for k in schema.keys() if getattr(k, "schema", None) == simulation_key)

    def _resolve_default(marker: object) -> Any:
        """Helper to resolve voluptuous default values."""
        if hasattr(marker, "default"):
            dv = getattr(marker, "default")
            return dv() if callable(dv) else dv
        return None

    # Default should be False (simulation disabled)
    assert _resolve_default(simulation_marker) is False

    # Now test submitting with simulation mode enabled
    user_input = {
        ConfKeys.ENABLED.value: True,
        ConfKeys.SIMULATING.value: True,  # Enable simulation mode
        ConfKeys.WEATHER_ENTITY_ID.value: "weather.test",
        ConfKeys.SUN_ELEVATION_THRESHOLD.value: 20,
    }

    result = await flow.async_step_init(user_input)
    result_dict = cast(dict[str, Any], result)

    # Verify successful submission with simulation mode enabled
    assert result_dict["type"] == "create_entry"
    assert result_dict["data"][ConfKeys.SIMULATING.value] is True


async def test_options_flow_simulation_mode_with_existing_config() -> None:
    """Test simulation mode handling when it's already configured in existing data/options.

    This test verifies that existing simulation mode configuration is properly
    read from data/options and displayed as defaults in the options form.
    """
    # Start with simulation mode already enabled in data
    data = {
        ConfKeys.COVERS.value: ["cover.test"],
        ConfKeys.SIMULATING.value: True,
    }

    # Override with simulation disabled in options
    options = {
        ConfKeys.SIMULATING.value: False,
    }

    flow = OptionsFlowHandler(create_options_flow_mock_entry(data, options))

    # Generate form and check that options value takes precedence
    result = await flow.async_step_init()
    result_dict = cast(dict[str, Any], result)
    schema = result_dict["data_schema"].schema

    simulation_marker = next(k for k in schema.keys() if getattr(k, "schema", None) == ConfKeys.SIMULATING.value)

    def _resolve_default(marker: object) -> Any:
        """Helper to resolve voluptuous default values."""
        if hasattr(marker, "default"):
            dv = getattr(marker, "default")
            return dv() if callable(dv) else dv
        return None

    # Should use options value (False) instead of data value (True)
    assert _resolve_default(simulation_marker) is False
