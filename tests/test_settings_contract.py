from dataclasses import fields

from custom_components.smart_cover_automation.config import (
    CONF_SPECS,
    ConfKeys,
    ResolvedConfig,
    validate_settings_contract,
)


def test_settings_contract_validator_passes():
    # Should not raise when everything is consistent
    validate_settings_contract()


def test_keys_and_defaults_registry_complete_mirrors_contract():
    enum_names = {k.value for k in ConfKeys}
    spec_names = {k.value for k in CONF_SPECS.keys()}
    dc_names = {f.name for f in fields(ResolvedConfig)}

    assert enum_names == spec_names, (
        f"ConfKeys vs CONF_SPECS mismatch:\nmissing_in_specs={enum_names - spec_names}\nextra_in_specs={spec_names - enum_names}"
    )
    assert enum_names == dc_names, (
        f"ConfKeys vs ResolvedConfig mismatch:\nmissing_in_dc={enum_names - dc_names}\nextra_in_dc={dc_names - enum_names}"
    )


def test_no_none_defaults_in_specs():
    none_defaults = [k.value for k, spec in CONF_SPECS.items() if spec.default is None]
    assert not none_defaults, f"None defaults found in CONF_SPECS: {none_defaults}"
