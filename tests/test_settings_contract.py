"""Tests for configuration settings contract validation and consistency.

This module contains critical tests that ensure the integrity and consistency
of the Smart Cover Automation configuration system. These tests act as a
"contract" that prevents configuration-related bugs by validating that all
configuration components are properly synchronized.

The configuration system consists of three key components that must stay in sync:
1. **ConfKeys Enum**: Defines all valid configuration key names
2. **CONF_SPECS Dictionary**: Defines validation rules and defaults for each key
3. **ResolvedConfig Dataclass**: Defines the runtime configuration structure

Contract validation ensures:
- No configuration keys are missing from any component
- All configuration keys have proper validation specifications
- All configuration keys have non-None default values
- The configuration system remains internally consistent

These tests are essential for preventing runtime configuration errors and
ensuring that new configuration options are properly integrated across
all system components. They act as a safety net that catches configuration
inconsistencies during development before they can cause user-facing issues.
"""

from dataclasses import fields

from custom_components.smart_cover_automation.config import (
    CONF_SPECS,
    ConfKeys,
    ResolvedConfig,
    validate_settings_contract,
)


def test_settings_contract_validator_passes():
    """Test that the built-in configuration contract validator passes without errors.

    This test runs the internal validate_settings_contract() function which performs
    comprehensive checks to ensure all configuration components are consistent.
    The validator checks for:
    - Enum/spec/dataclass synchronization
    - Proper default value assignment
    - Type consistency across components

    If this test fails, it indicates a fundamental configuration system issue
    that must be resolved before the integration can function properly.
    Any configuration changes that break this contract will cause runtime errors.
    """
    # Should not raise any exceptions when configuration system is consistent
    validate_settings_contract()


def test_keys_and_defaults_registry_complete_mirrors_contract():
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


def test_no_none_defaults_in_specs():
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
