"""Config flow and options flow for Smart Cover Automation integration."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
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

            # Validate temperature thresholds
            max_key = ConfKeys.MAX_TEMPERATURE.value
            min_key = ConfKeys.MIN_TEMPERATURE.value
            has_max = max_key in user_input
            has_min = min_key in user_input

            # If only one threshold is provided, mark the counterpart as required
            if has_max ^ has_min:
                if has_max:
                    errors[min_key] = const.ERROR_REQUIRED_WITH_MAX_TEMPERATURE
                    const.LOGGER.error(f"{min_key} required when {max_key} is provided")
                else:
                    errors[max_key] = const.ERROR_REQUIRED_WITH_MIN_TEMPERATURE
                    const.LOGGER.error(f"{max_key} required when {min_key} is provided")
            # If both are provided, validate the range
            elif has_max and has_min:
                max_temp = user_input[max_key]
                min_temp = user_input[min_key]
                if max_temp <= min_temp:
                    errors["base"] = const.ERROR_INVALID_TEMPERATURE_RANGE
                    const.LOGGER.error(f"Invalid temperature range: max={max_temp} <= min={min_temp}")

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
                    vol.Required(ConfKeys.COVERS.value): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=Platform.COVER,
                            multiple=True,
                        ),
                    ),
                    # Optional temperature thresholds
                    vol.Optional(
                        ConfKeys.MAX_TEMPERATURE.value,
                        default=CONF_SPECS[ConfKeys.MAX_TEMPERATURE].default,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=40,
                            step=0.5,
                            unit_of_measurement=UnitOfTemperature.CELSIUS,
                        ),
                    ),
                    vol.Optional(
                        ConfKeys.MIN_TEMPERATURE.value,
                        default=CONF_SPECS[ConfKeys.MIN_TEMPERATURE].default,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=40,
                            step=0.5,
                            unit_of_measurement=UnitOfTemperature.CELSIUS,
                        ),
                    ),
                    vol.Optional(
                        ConfKeys.AZIMUTH_TOLERANCE.value,
                        default=CONF_SPECS[ConfKeys.AZIMUTH_TOLERANCE].default,
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
            key = f"{cover}_{const.COVER_AZIMUTH}"
            raw = options.get(key, data.get(key))
            direction_azimuth: float | None = to_float_or_none(raw)

            if direction_azimuth is not None:
                direction_fields[vol.Optional(key, default=direction_azimuth)] = selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=359, step=0.1, unit_of_measurement="°")
                )
            else:
                direction_fields[vol.Optional(key)] = selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=359, step=0.1, unit_of_measurement="°")
                )

        enabled_default = bool(resolved_settings.enabled)
        temp_sensor_default = str(resolved_settings.temp_sensor_entity_id)
        threshold_default = float(resolved_settings.sun_elevation_threshold)
        azimuth_tol_default = int(resolved_settings.azimuth_tolerance)

        schema_dict: dict[vol.Marker, object] = {
            vol.Optional(ConfKeys.ENABLED.value, default=enabled_default): selector.BooleanSelector(),
            vol.Optional(
                ConfKeys.VERBOSE_LOGGING.value,
                default=bool(resolved_settings.verbose_logging),
            ): selector.BooleanSelector(),
            # Allow editing the list of covers without changing the unique_id
            vol.Optional(
                ConfKeys.COVERS.value,
                default=covers,
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=Platform.COVER,
                    multiple=True,
                ),
            ),
            vol.Optional(
                ConfKeys.TEMP_SENSOR_ENTITY_ID.value,
                default=temp_sensor_default,
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain=Platform.SENSOR)),
            vol.Optional(
                ConfKeys.SUN_ELEVATION_THRESHOLD.value,
                default=threshold_default,
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=90, step=1)),
            vol.Optional(
                ConfKeys.AZIMUTH_TOLERANCE.value,
                default=azimuth_tol_default,
            ): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=180, step=1, unit_of_measurement="°")),
        }

        # Compute safe default for max_closure
        max_closure_default = int(resolved_settings.max_closure)

        schema_dict[vol.Optional(ConfKeys.MAX_CLOSURE.value, default=max_closure_default)] = selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
        )

        # Add dynamic direction fields at the end
        schema_dict.update(direction_fields)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
