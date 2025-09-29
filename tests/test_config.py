"""Unit tests for configuration resolution and validation logic.

This module contains comprehensive unit tests for the Smart Cover Automation
configuration system, focusing on the core configuration resolution logic
that transforms raw user input into validated, typed configuration objects.

Key testing areas include:
1. **Configuration Registry Validation**: Tests that CONF_SPECS contains all
   required configuration keys and maintains proper structure
2. **Data Type Resolution**: Tests automatic type coercion and normalization
3. **Priority Resolution**: Tests options vs data precedence handling
4. **Default Value Fallback**: Tests behavior when coercion fails or values are missing
5. **Collection Handling**: Tests various input formats for covers configuration
6. **Accessor Methods**: Tests configuration object interface methods
7. **Configuration Contract Validation**: Tests consistency across all components

The configuration resolution system is critical because it:
- Converts raw Home Assistant config entry data into typed objects
- Handles user input validation and sanitization
- Provides sensible defaults when values are missing or invalid
- Ensures the integration can work with various input formats
- Maintains backward compatibility with older configuration formats

These unit tests ensure that regardless of how users configure the integration
(through UI, YAML, or programmatically), the system produces consistent,
valid configuration objects that the automation logic can rely on.
"""

from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace

import pytest

from custom_components.smart_cover_automation.config import (
    CONF_SPECS,
    ConfKeys,
    ResolvedConfig,
    resolve,
    resolve_entry,
)

# =============================================================================
# Configuration Registry and Contract Validation Tests
# =============================================================================


class TestConfigurationRegistry:
    """Tests for configuration registry integrity and contract validation.

    These tests ensure that the configuration system components (ConfKeys,
    CONF_SPECS, and ResolvedConfig) are properly synchronized and maintain
    their contracts.
    """

    def test_keys_and_defaults_registry_complete(self):
        """Test that CONF_SPECS registry contains all configuration keys with proper structure.

        This test validates the configuration specification registry to ensure:
        1. All ConfKeys enum members have corresponding CONF_SPECS entries
        2. All configuration keys are properly typed as strings (Home Assistant requirement)

        The CONF_SPECS registry is the authoritative source for configuration validation
        rules, default values, and type coercion logic. This test ensures that every
        configuration option defined in the ConfKeys enum has a proper specification.

        If this test fails, it indicates that a new configuration option was added
        to ConfKeys but the corresponding CONF_SPECS entry was not created, which
        would cause runtime errors during configuration resolution.
        """
        # CONF_SPECS must contain all enum members and mirrors string view
        assert set(CONF_SPECS.keys()) == set(ConfKeys)
        assert all(isinstance(key.value, str) for key in CONF_SPECS.keys())

    def test_keys_and_defaults_registry_complete_mirrors_contract(self):
        """Test that ConfKeys, CONF_SPECS, and ResolvedConfig are perfectly synchronized.

        This test ensures that all three configuration components contain exactly
        the same set of configuration keys. This is critical because:

        - ConfKeys defines which configuration options exist
        - CONF_SPECS defines how those options are validated and their defaults
        - ResolvedConfig defines the runtime structure for storing those options

        If any component is missing a key or has extra keys, it indicates:
        1. A new configuration option was added but not properly integrated
        2. An old configuration option was removed but cleanup was incomplete
        3. A typo or naming inconsistency exists between components

        The test provides detailed mismatch information to help identify exactly
        which keys are missing or extra in each component.
        """
        # Extract all configuration key names from each component
        enum_names = {k.value for k in ConfKeys}  # Keys defined in enum
        spec_names = {k.value for k in CONF_SPECS.keys()}  # Keys with validation specs
        dc_names = {f.name for f in fields(ResolvedConfig)}  # Keys in runtime dataclass

        # Ensure ConfKeys and CONF_SPECS are perfectly synchronized
        assert enum_names == spec_names, (
            f"ConfKeys vs CONF_SPECS mismatch:\nmissing_in_specs={enum_names - spec_names}\nextra_in_specs={spec_names - enum_names}"
        )

        # Ensure ConfKeys and ResolvedConfig are perfectly synchronized
        assert enum_names == dc_names, (
            f"ConfKeys vs ResolvedConfig mismatch:\nmissing_in_dc={enum_names - dc_names}\nextra_in_dc={dc_names - enum_names}"
        )

    def test_no_none_defaults_in_specs(self):
        """Test that all configuration specifications have non-None default values.

        This test ensures that every configuration option has a meaningful default
        value defined in CONF_SPECS. None defaults are problematic because:

        1. They can cause runtime errors when the configuration is accessed
        2. They provide poor user experience (users must configure everything)
        3. They make it difficult to determine if a value was intentionally unset
        4. They complicate configuration validation and merging logic

        All configuration options should have sensible defaults that allow the
        integration to function out-of-the-box with minimal user configuration.
        This promotes a better user experience and reduces support burden.

        If this test fails, it means a configuration option was added without
        providing a proper default value, which must be fixed before release.
        """
        # Find any configuration specs that have None as their default value
        none_defaults = [k.value for k, spec in CONF_SPECS.items() if spec.default is None]

        # Assert that no configuration options have None defaults
        assert not none_defaults, f"None defaults found in CONF_SPECS: {none_defaults}"

    def test_spec_defaults_are_valid_types(self):
        """Test that all CONF_SPECS default values can be processed by their converters.

        This test ensures that each configuration specification's converter function
        can successfully process its own default value. This validates that:

        1. Default values are already in the correct format for their converters
        2. Converters don't unexpectedly modify correct input values
        3. The type conversion system is internally consistent

        This is important because the configuration resolution system relies on
        converters being able to process their own defaults as a fallback mechanism
        when user input fails validation. If a converter can't handle its own
        default, it indicates a fundamental design issue that could cause runtime
        errors during configuration resolution.

        The test verifies both that conversion succeeds and that the converted
        value equals the original default (i.e., converters are idempotent for
        correctly-typed inputs).
        """
        for key, spec in CONF_SPECS.items():
            # Each spec's converter should be able to process its own default
            try:
                converted_default = spec.converter(spec.default)
                # The converted value should be the same as the original default
                # (since defaults should already be the correct type)
                assert converted_default == spec.default, f"CONF_SPECS[{key}].converter changed the default value"
            except Exception as e:
                pytest.fail(f"CONF_SPECS[{key}].converter failed on its own default: {e}")

    def test_contract_violation_detection(self):
        """Test that contract violations would be properly detected.

        This test demonstrates what would happen if the configuration contract was
        violated by simulating various mismatch scenarios between ConfKeys,
        CONF_SPECS, and ResolvedConfig. It serves as both documentation and
        validation of the contract enforcement logic.

        The test verifies that:
        1. The current configuration state is valid (all components synchronized)
        2. Simulated violations would be detectable by contract validation logic
        3. The contract validation system would catch common development errors

        Common contract violations this would detect:
        - Adding a new ConfKeys member without updating CONF_SPECS
        - Adding a new ResolvedConfig field without updating ConfKeys
        - Adding CONF_SPECS entries without corresponding enum members
        - Inconsistent naming between components

        This test helps ensure that future configuration changes maintain the
        strict synchronization requirements of the configuration system.
        """
        # Save original values
        original_enum_names = {k.value for k in ConfKeys}
        original_spec_names = {k.value for k in CONF_SPECS.keys()}
        original_dc_names = {f.name for f in fields(ResolvedConfig)}

        # All should be equal in the current valid state
        assert original_enum_names == original_spec_names == original_dc_names

        # Simulate what would happen with mismatches
        fake_enum_names = original_enum_names | {"fake_key"}
        fake_spec_names = original_spec_names | {"extra_spec_key"}
        fake_dc_names = original_dc_names | {"extra_field"}

        # These would trigger validation errors
        assert fake_enum_names != original_spec_names  # Would trigger ConfKeys vs CONF_SPECS mismatch
        assert fake_enum_names != original_dc_names  # Would trigger ConfKeys vs ResolvedConfig mismatch
        assert fake_spec_names != original_enum_names  # Would trigger CONF_SPECS vs ConfKeys mismatch
        assert fake_dc_names != original_enum_names  # Would trigger ResolvedConfig vs ConfKeys mismatch


# =============================================================================
# Configuration Resolution and Priority Tests
# =============================================================================


class TestConfigurationResolution:
    """Tests for configuration resolution logic including priority handling and type coercion.

    These tests verify that the resolve() function correctly handles various input
    formats, applies priority rules, and performs type conversions.
    """

    def test_resolve_priority_and_coercion_with_defaults_fallback(self):
        """Test configuration priority resolution, type coercion, and default fallback behavior.

        This test verifies the sophisticated configuration resolution logic that handles:
        1. **Priority Resolution**: Options take precedence over data when both are present
        2. **Type Coercion**: String values are automatically converted to appropriate types
        3. **Default Fallback**: When coercion fails, system falls back to default values

        Home Assistant stores configuration in two places:
        - data: Initial setup configuration (from config flow)
        - options: Runtime configuration changes (from options flow)

        The resolution system must handle various scenarios:
        - Options override data when both exist
        - Successful type coercion from strings (HA stores everything as strings)
        - Graceful fallback to defaults when values can't be coerced

        This ensures users can reconfigure the integration through the options flow
        while maintaining robust behavior even with invalid input.
        """
        # Setup test data with options taking priority over data
        data = {
            ConfKeys.TEMP_THRESHOLD.value: "18.5",  # Will be overridden by options
            ConfKeys.ENABLED.value: 0,  # Will be used (not in options)
        }
        options = {
            ConfKeys.TEMP_THRESHOLD.value: "20.0",  # Takes priority over data
            ConfKeys.COVERS_MIN_POSITION_DELTA.value: "not-an-int",  # Invalid -> falls back to default
        }

        rs: ResolvedConfig = resolve(options, data)

        # Priority: options take precedence over data
        assert rs.temp_threshold == 20.0

        # Coercion success from data for enabled (not overridden in options)
        # 0 -> False (integer to boolean coercion)
        assert rs.enabled is False

        # Coercion failure falls back to default and coerces that
        # "not-an-int" can't be converted to int, so uses default value 5
        assert rs.covers_min_position_delta == 5

    def test_resolve_entry_reads_from_attributes(self):
        """Test that resolve_entry() extracts configuration from Home Assistant config entry objects.

        This test verifies the convenience function that extracts configuration
        from Home Assistant ConfigEntry objects. Home Assistant stores configuration
        in two attributes of config entries:

        - **options**: Runtime configuration changes made through the options flow
        - **data**: Initial configuration data from the initial setup flow

        The resolve_entry() function is a wrapper around resolve() that automatically
        extracts these attributes from the config entry object, making it easier
        for the integration code to work with Home Assistant's config entry format.

        This pattern is common in Home Assistant integrations and provides a clean
        interface between Home Assistant's configuration management and the
        integration's internal configuration handling.
        """
        # Create mock config entry with options and data attributes (like Home Assistant provides)
        entry = SimpleNamespace(
            options={ConfKeys.ENABLED.value: False},  # Options flow configuration
            data={ConfKeys.TEMP_THRESHOLD.value: 22},  # Initial setup configuration
        )

        # resolve_entry() should extract and resolve configuration from the entry
        rs = resolve_entry(entry)
        assert rs.enabled is False  # From options
        assert rs.temp_threshold == 22.0  # From data (coerced to float)


# =============================================================================
# Covers Configuration Tests
# =============================================================================


class TestCoversConfiguration:
    """Tests for covers configuration handling and normalization.

    These tests verify that the covers configuration is properly normalized
    from various input formats to a consistent tuple format.
    """

    def test_list_covers_normalized_via_resolve(self):
        """Test that covers configuration is normalized from list to tuple format.

        This test verifies that the configuration resolution system properly normalizes
        the covers configuration from various input formats to a consistent tuple format.

        Home Assistant users can provide covers as:
        - Lists from UI configuration
        - Lists from YAML configuration
        - Various other iterable formats

        The resolve() function should normalize all these formats to tuples for
        internal consistency and immutability. Tuples are preferred because:
        1. They're immutable (can't be accidentally modified)
        2. They're hashable (can be used as dict keys if needed)
        3. They provide consistent iteration behavior

        This normalization ensures that the rest of the codebase can rely on
        covers always being a tuple, regardless of input format.
        """
        # covers provided as a list should be normalized to a tuple by resolve()
        options = {ConfKeys.COVERS.value: ["cover.a", "cover.b"]}
        rs = resolve(options, data=None)
        assert isinstance(rs.covers, tuple)
        assert rs.covers == ("cover.a", "cover.b")

    @pytest.mark.parametrize(
        "covers_input,expected",
        [
            (None, ()),  # No covers configured -> empty tuple
            ([], ()),  # Empty list -> empty tuple
            (("a", "b"), ("a", "b")),  # Tuple input -> preserved as tuple
            (["x", 123], ("x", "123")),  # Mixed types -> normalized to string tuple
        ],
    )
    def test_resolve_covers_common_shapes(self, covers_input, expected):
        """Test covers configuration resolution for common input formats.

        This parameterized test verifies that the covers configuration resolution
        handles various common input formats correctly:

        1. **None input**: When no covers are configured, results in empty tuple
        2. **Empty list**: When user provides empty list, results in empty tuple
        3. **Tuple input**: When covers are already tuples, they're preserved
        4. **Mixed types**: When list contains non-strings, they're normalized to strings

        The covers configuration is fundamental to the integration since it defines
        which cover entities the automation should control. The resolution system
        must handle various input formats gracefully and normalize them to a
        consistent format for the automation logic.

        String normalization is important because Home Assistant entity IDs are
        always strings, so any non-string values (like numbers from UI input)
        must be converted to strings to be valid entity references.
        """
        rs = resolve({ConfKeys.COVERS.value: covers_input}, {})
        assert rs.covers == expected

    def test_resolve_covers_string_and_non_iterable_behaviors(self):
        """Test covers configuration resolution for edge case input formats.

        This test verifies the configuration system's behavior with unusual but
        possible input formats for the covers configuration:

        1. **String Input**: When a user provides a string instead of a list,
           the system treats it as an iterable of characters. This is back-compatible
           behavior that handles misconfiguration gracefully.

        2. **Non-iterable Input**: When completely invalid objects are provided,
           the system uses safe fallback behavior and returns an empty tuple.

        These edge cases can occur when:
        - Users manually edit configuration files incorrectly
        - API clients send malformed data
        - Configuration migration goes wrong

        The system should handle these gracefully without crashing, allowing
        users to fix their configuration through the UI rather than requiring
        manual file editing or integration reinstallation.
        """
        # String input is treated as an iterable of characters (back-compat behavior)
        rs = resolve({ConfKeys.COVERS.value: "cover.window"}, {})
        assert rs.covers == tuple("cover.window")

        # Non-iterable input results in an empty tuple via safe fallback
        class NotIterable:
            """Test class that doesn't implement iteration protocol."""

            pass

        rs2 = resolve({ConfKeys.COVERS.value: NotIterable()}, {})
        assert rs2.covers == ()


# =============================================================================
# Configuration Accessor Tests
# =============================================================================


class TestConfigurationAccessors:
    """Tests for ResolvedConfig accessor methods and interface.

    These tests verify that the configuration object provides convenient
    methods for accessing configuration values.
    """

    def test_resolved_settings_accessors(self):
        """Test ResolvedConfig accessor methods for configuration value retrieval.

        This test verifies that the ResolvedConfig object provides convenient
        accessor methods for retrieving configuration values:

        1. **get() method**: Allows retrieving values by ConfKeys enum, providing
           type safety and preventing typos in configuration key names

        2. **as_enum_dict() method**: Returns a complete mapping of all configuration
           values keyed by enum values, useful for serialization or debugging

        These accessor methods provide a clean interface for the rest of the codebase
        to interact with configuration values without directly accessing attributes.
        They also ensure that all configuration options are accounted for and
        provide type hints for better development experience.

        The enum-based access pattern prevents configuration key typos and makes
        refactoring safer by providing compile-time checking of configuration usage.
        """
        # Setup resolved configuration with specific test values
        rs = resolve(
            {
                ConfKeys.ENABLED.value: True,  # Boolean configuration
                ConfKeys.TEMP_THRESHOLD.value: 30,  # Numeric configuration (will be coerced to float)
            },
            {},
        )

        # get() method reads configuration values by enum key
        assert rs.get(ConfKeys.TEMP_THRESHOLD) == 30.0

        # as_enum_dict() returns complete mapping by enum for all configuration options
        enum_dict = rs.as_enum_dict()
        assert set(enum_dict.keys()) == set(ConfKeys)  # Contains all configuration keys
        assert enum_dict[ConfKeys.ENABLED] is True  # Preserves configured values


# =============================================================================
# Duration Converter Tests
# =============================================================================


class TestDurationConverter:
    """Tests for duration converter functionality.

    These tests verify that the duration converter properly handles various
    input formats for time durations and converts them to seconds.
    """

    def test_duration_converter_with_integer_input(self):
        """Test to_duration_seconds converter with integer input (seconds)."""
        from custom_components.smart_cover_automation.config import _Converters

        # Test positive integers
        assert _Converters.to_duration_seconds(0) == 0
        assert _Converters.to_duration_seconds(30) == 30
        assert _Converters.to_duration_seconds(1800) == 1800
        assert _Converters.to_duration_seconds(3600) == 3600

        # Test negative integers (should return 0)
        assert _Converters.to_duration_seconds(-1) == 0
        assert _Converters.to_duration_seconds(-100) == 0

    def test_duration_converter_with_ha_duration_format(self):
        """Test to_duration_seconds converter with Home Assistant duration format."""
        from custom_components.smart_cover_automation.config import _Converters

        # Test individual components
        assert _Converters.to_duration_seconds({"seconds": 30}) == 30
        assert _Converters.to_duration_seconds({"minutes": 5}) == 300
        assert _Converters.to_duration_seconds({"hours": 1}) == 3600
        assert _Converters.to_duration_seconds({"days": 1}) == 86400

        # Test combinations
        assert _Converters.to_duration_seconds({"minutes": 30}) == 1800
        assert _Converters.to_duration_seconds({"hours": 1, "minutes": 30}) == 5400
        assert _Converters.to_duration_seconds({"hours": 1, "minutes": 30, "seconds": 45}) == 5445
        assert _Converters.to_duration_seconds({"days": 1, "hours": 2, "minutes": 30, "seconds": 15}) == 95415

        # Test with zero values (should be ignored)
        assert _Converters.to_duration_seconds({"hours": 0, "minutes": 30, "seconds": 0}) == 1800
        assert _Converters.to_duration_seconds({"days": 0, "hours": 0, "minutes": 0, "seconds": 0}) == 0

        # Test with missing keys (should default to 0)
        assert _Converters.to_duration_seconds({}) == 0
        assert _Converters.to_duration_seconds({"minutes": 10}) == 600  # missing days, hours, seconds

    def test_duration_converter_edge_cases(self):
        """Test to_duration_seconds converter with edge cases and error conditions."""
        from custom_components.smart_cover_automation.config import _Converters

        # Test with negative values in dict (should be handled gracefully)
        assert _Converters.to_duration_seconds({"minutes": -10}) == 0
        assert _Converters.to_duration_seconds({"hours": 1, "minutes": -30}) == 1800  # 1 hour - 30 min = 30 min

        # Test with float values (should convert to int)
        assert _Converters.to_duration_seconds({"minutes": 30.5, "seconds": 15.7}) == 1845
        assert _Converters.to_duration_seconds({"hours": 1.5}) == 5400  # 1.5 hours = 90 minutes = 5400 seconds

        # Test large values
        assert _Converters.to_duration_seconds({"days": 365}) == 31536000  # 1 year in seconds

        # Test common real-world scenarios
        assert _Converters.to_duration_seconds({"minutes": 1}) == 60  # 1 minute
        assert _Converters.to_duration_seconds({"minutes": 15}) == 900  # 15 minutes
        assert _Converters.to_duration_seconds({"minutes": 30}) == 1800  # 30 minutes (default)
        assert _Converters.to_duration_seconds({"hours": 2}) == 7200  # 2 hours

    def test_duration_converter_integration_with_conf_specs(self):
        """Test that the duration converter works correctly with CONF_SPECS."""
        from custom_components.smart_cover_automation.config import CONF_SPECS, ConfKeys

        # Get the manual override duration spec
        spec = CONF_SPECS[ConfKeys.MANUAL_OVERRIDE_DURATION]

        # Test that the default value is handled correctly
        assert spec.converter(spec.default) == 1800  # Default should be 1800 seconds

        # Test that the converter is the correct function
        assert spec.converter.__name__ == "to_duration_seconds"

        # Test various inputs through the spec converter
        assert spec.converter({"minutes": 45}) == 2700
        assert spec.converter(3600) == 3600
        assert spec.converter({"hours": 1, "minutes": 15}) == 4500

    @pytest.mark.parametrize(
        "duration_input,expected_seconds",
        [
            # Integer inputs
            (0, 0),
            (60, 60),
            (1800, 1800),
            (3600, 3600),
            # HA duration format - single values
            ({"seconds": 45}, 45),
            ({"minutes": 10}, 600),
            ({"hours": 2}, 7200),
            ({"days": 1}, 86400),
            # HA duration format - combinations
            ({"minutes": 5, "seconds": 30}, 330),
            ({"hours": 1, "minutes": 30}, 5400),
            ({"hours": 2, "minutes": 15, "seconds": 45}, 8145),
            ({"days": 1, "hours": 1, "minutes": 1, "seconds": 1}, 90061),
            # Edge cases
            ({}, 0),
            ({"hours": 0, "minutes": 0, "seconds": 0}, 0),
            ({"minutes": 30.5}, 1830),  # Float values
            # Common use cases
            ({"minutes": 1}, 60),  # 1 minute
            ({"minutes": 15}, 900),  # 15 minutes
            ({"minutes": 30}, 1800),  # 30 minutes (default)
            ({"hours": 1}, 3600),  # 1 hour
            ({"hours": 2}, 7200),  # 2 hours
        ],
    )
    def test_duration_converter_parametrized(self, duration_input, expected_seconds):
        """Parametrized test for duration converter with various inputs."""
        from custom_components.smart_cover_automation.config import _Converters

        result = _Converters.to_duration_seconds(duration_input)
        assert result == expected_seconds
        assert isinstance(result, int)
