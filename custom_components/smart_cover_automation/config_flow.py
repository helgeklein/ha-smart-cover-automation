"""Config flow and options flow for Smart Cover Automation integration."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import STATE_UNAVAILABLE, Platform, UnitOfTemperature
from homeassistant.helpers import selector

from . import const
from .config import CONF_SPECS, ConfKeys, resolve
from .util import to_float_or_none


class FlowHandler(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Config flow for the integration."""

    # Schema version
    # When changing the schema, increment the version and implement async_migrate_entry
    VERSION = 1
    # Explicit domain attribute for tests referencing FlowHandler.domain
    domain = const.DOMAIN

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Invoked when the user adds the integration from the UI.

        HA calls async_step_user(None) to show the form, then calls it again with a dict after submit.
        It's called again on validation errors (to re-display the form) until it returns create_entry or aborts.
        It's not used for editing options (that's OptionsFlowHandler.async_step_init).

        Error messages are retured in the errors dict:
        - The key "base" is for general errors not associated with a specific field.
        - Values like "invalid_cover" are keys that are mapped to strings defined in <lang>.json.
        """
        errors = {}

        # Ensure only a single instance of this integration can be configured
        # Guard against tests/mocks where hass/config_entries may be incomplete
        try:
            if getattr(self, "hass", None) is not None:
                current_entries = self._async_current_entries()
                if isinstance(current_entries, list) and len(current_entries) > 0:
                    return self.async_abort(reason=const.ABORT_SINGLE_INSTANCE_ALLOWED)
        except Exception:  # pragma: no cover - defensive against MagicMock behavior in tests
            pass

        # Initial call: user_input is None -> show the form to the user
        if user_input is None:
            return self._show_user_form_config()

        # Subsequent calls: user_input has form data -> validate user data and create entry
        try:
            # Validate covers
            invalid_covers = []
            for cover in user_input[ConfKeys.COVERS.value]:
                state = self.hass.states.get(cover)
                if not state:
                    invalid_covers.append(cover)
                elif state.state == STATE_UNAVAILABLE:
                    const.LOGGER.warning(f"Cover {cover} is currently unavailable but will be configured")

            if invalid_covers:
                errors["base"] = const.ERROR_INVALID_COVER
                const.LOGGER.error(f"Invalid covers selected: {invalid_covers}")

            if not errors:
                # Create a permanent unique ID for this config entry
                unique_id = str(uuid.uuid4())
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Persist provided data
                data = dict(user_input)

                # Create a new HA config entry with the provided data
                return self.async_create_entry(
                    title=const.INTEGRATION_NAME,
                    data=data,
                )

        except (KeyError, ValueError, TypeError) as err:
            const.LOGGER.exception(f"Configuration validation error: {err}")
            errors["base"] = const.ERROR_INVALID_CONFIG

        # Validation error: show the form to the user again
        return self._show_user_form_config(errors)

    def _show_user_form_config(self, errors: dict[str, str] | None = None) -> config_entries.ConfigFlowResult:
        """Render the initial user form (or re-display after validation errors)."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    # Covers
                    vol.Required(ConfKeys.COVERS.value): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=Platform.COVER,
                            multiple=True,
                        ),
                    ),
                    # Temperature threshold
                    # TODO: needs to be changeable later, too (options flow)
                    vol.Optional(
                        ConfKeys.TEMP_THRESHOLD.value,
                        default=CONF_SPECS[ConfKeys.TEMP_THRESHOLD].default,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-10,
                            max=40,
                            step=0.5,
                            unit_of_measurement=UnitOfTemperature.CELSIUS,
                        ),
                    ),
                    # Azimuth tolerance
                    vol.Optional(
                        ConfKeys.SUN_AZIMUTH_TOLERANCE.value,
                        default=CONF_SPECS[ConfKeys.SUN_AZIMUTH_TOLERANCE].default,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=180, step=1, unit_of_measurement="°"),
                    ),
                }
            ),
            errors=errors or {},
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Smart Cover Automation."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow.

        Avoid assigning to OptionsFlow.config_entry directly to prevent frame-helper
        warnings in tests; keep a private reference instead.
        """
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Invoked when the user clicks the gear icon to bring up the integration's options dialog.

        HA calls async_step_init(None) to show the form, then calls it again with a dict after submit.
        """
        # Subsequent calls: user_input has form data -> store the options and finish
        if user_input is not None:
            # Clean up any orphaned cover-specific settings if covers were removed
            # Only do this if the user actually modified the covers list
            if ConfKeys.COVERS.value in user_input:
                covers_in_input = user_input.get(ConfKeys.COVERS.value, [])
                cleaned_input = dict(user_input)

                # Remove azimuth settings for covers that are no longer configured
                keys_to_remove = []
                for key in cleaned_input.keys():
                    if key.endswith(f"_{const.COVER_SFX_AZIMUTH}"):
                        cover_entity = key.replace(f"_{const.COVER_SFX_AZIMUTH}", "")
                        if cover_entity not in covers_in_input:
                            keys_to_remove.append(key)

                for key in keys_to_remove:
                    cleaned_input.pop(key, None)

                user_input = cleaned_input

            # Persist options; HA will trigger entry update and reload
            return self.async_create_entry(title="Options", data=user_input)

        # Initial call: user_input is None -> show the form to the user

        data = dict(self._config_entry.data)
        options = dict(self._config_entry.options or {})
        resolved_settings = resolve(options, data)

        # Build dynamic fields for per-cover directions as numeric azimuth angles (0-359)
        covers: list[str] = list(resolved_settings.covers)
        direction_fields: dict[vol.Marker, object] = {}

        for cover in covers:
            key = f"{cover}_{const.COVER_SFX_AZIMUTH}"
            raw = options.get(key, data.get(key))
            direction_azimuth: float | None = to_float_or_none(raw)

            # Create a more user-friendly label for the field
            cover_name = cover.replace("cover.", "").replace("_", " ").title()
            description = f"Azimuth direction for {cover_name}"

            # Use a consistent selector configuration
            number_selector = selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=359, step=0.1, unit_of_measurement="°", mode=selector.NumberSelectorMode.BOX)
            )

            if direction_azimuth is not None:
                direction_fields[vol.Optional(key, default=direction_azimuth, description=description)] = number_selector
            else:
                direction_fields[vol.Optional(key, description=description)] = number_selector

        # Extract default values from resolved settings
        enabled_default = resolved_settings.enabled
        simulating_default = resolved_settings.simulating
        threshold_default = resolved_settings.sun_elevation_threshold
        azimuth_tol_default = resolved_settings.sun_azimuth_tolerance

        # Build the schema with logical field grouping
        schema_dict: dict[vol.Marker, object] = {}

        # === GLOBAL AUTOMATION SETTINGS ===
        schema_dict[vol.Optional(ConfKeys.ENABLED.value, default=enabled_default)] = selector.BooleanSelector()
        schema_dict[vol.Optional(ConfKeys.SIMULATING.value, default=simulating_default)] = selector.BooleanSelector()
        schema_dict[vol.Optional(ConfKeys.VERBOSE_LOGGING.value, default=resolved_settings.verbose_logging)] = selector.BooleanSelector()

        # === COVER CONFIGURATION ===
        # Allow editing the list of covers without changing the unique_id
        schema_dict[vol.Optional(ConfKeys.COVERS.value, default=covers)] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=Platform.COVER,
                multiple=True,
            ),
        )

        # === TEMPERATURE SETTINGS ===
        schema_dict[vol.Optional(ConfKeys.TEMP_SENSOR_ENTITY_ID.value)] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=Platform.WEATHER,
                device_class=SensorDeviceClass.TEMPERATURE,
            )
        )

        # === SUN POSITION SETTINGS ===
        schema_dict[vol.Optional(ConfKeys.SUN_ELEVATION_THRESHOLD.value, default=threshold_default)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=90, step=1, unit_of_measurement="°")
        )
        schema_dict[vol.Optional(ConfKeys.SUN_AZIMUTH_TOLERANCE.value, default=azimuth_tol_default)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=180, step=1, unit_of_measurement="°")
        )

        # === COVER BEHAVIOR SETTINGS ===
        schema_dict[vol.Optional(ConfKeys.COVERS_MAX_CLOSURE.value, default=resolved_settings.covers_max_closure)] = (
            selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%"))
        )

        # === PER-COVER AZIMUTH DIRECTIONS ===
        # Add dynamic direction fields, sorted for consistent ordering
        if direction_fields:
            # Sort covers alphabetically for better user experience
            sorted_direction_items = sorted(direction_fields.items(), key=lambda x: str(x[0]))

            for field_key, field_selector in sorted_direction_items:
                schema_dict[field_key] = field_selector

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
