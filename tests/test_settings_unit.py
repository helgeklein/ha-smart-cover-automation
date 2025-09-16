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

from types import SimpleNamespace

import pytest

from custom_components.smart_cover_automation.config import (
    CONF_SPECS,
    ConfKeys,
    ResolvedConfig,
    resolve,
    resolve_entry,
)


def test_keys_and_defaults_registry_complete():
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


def test_list_covers_normalized_via_resolve():
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


def test_resolve_priority_and_coercion_with_defaults_fallback():
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


@pytest.mark.parametrize(
    "covers_input,expected",
    [
        (None, ()),  # No covers configured -> empty tuple
        ([], ()),  # Empty list -> empty tuple
        (("a", "b"), ("a", "b")),  # Tuple input -> preserved as tuple
        (["x", 123], ("x", "123")),  # Mixed types -> normalized to string tuple
    ],
)
def test_resolve_covers_common_shapes(covers_input, expected):
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


def test_resolve_covers_string_and_non_iterable_behaviors():
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


def test_resolved_settings_accessors():
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


def test_resolve_entry_reads_from_attributes():
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
