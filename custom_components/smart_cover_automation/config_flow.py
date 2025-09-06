"""Config flow and options flow for Smart Cover Automation integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import selector

from . import const


class FlowHandler(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Config flow for the integration."""

    VERSION = 1
    # Provide explicit domain attribute for tests referencing FlowHandler.domain
    domain = const.DOMAIN

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                # Validate covers exist and are available
                invalid_covers = []
                for cover in user_input[const.CONF_COVERS]:
                    state = self.hass.states.get(cover)
                    if not state:
                        invalid_covers.append(cover)
                    elif state.state == "unavailable":
                        const.LOGGER.warning(
                            "Cover %s is currently unavailable but will be configured",
                            cover,
                        )

                if invalid_covers:
                    errors["base"] = "invalid_cover"
                    const.LOGGER.error(
                        "Invalid covers selected: %s",
                        invalid_covers,
                    )

                # Validate temperature ranges if provided
                if (
                    const.CONF_MAX_TEMP in user_input
                    and const.CONF_MIN_TEMP in user_input
                ):
                    max_temp = user_input[const.CONF_MAX_TEMP]
                    min_temp = user_input[const.CONF_MIN_TEMP]
                    if max_temp <= min_temp:
                        errors["base"] = "invalid_temperature_range"
                        const.LOGGER.error(
                            "Invalid temperature range: max=%s <= min=%s",
                            max_temp,
                            min_temp,
                        )

                if not errors:
                    # Create unique ID based on the covers being automated
                    unique_id = "_".join(sorted(user_input[const.CONF_COVERS]))
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    # Persist provided data; single combined mode is implicit
                    data = dict(user_input)

                    return self.async_create_entry(
                        title=(
                            f"Cover Automation ({len(user_input[const.CONF_COVERS])} covers)"
                        ),
                        data=data,
                    )

            except (KeyError, ValueError, TypeError) as err:
                const.LOGGER.exception("Configuration validation error: %s", err)
                errors["base"] = "invalid_config"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(const.CONF_COVERS): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="cover",
                            multiple=True,
                        ),
                    ),
                    # Optional temperature thresholds used by combined mode
                    vol.Optional(
                        const.CONF_MAX_TEMP,
                        default=const.DEFAULT_MAX_TEMP,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=40,
                            step=0.5,
                            unit_of_measurement=UnitOfTemperature.CELSIUS,
                        ),
                    ),
                    vol.Optional(
                        const.CONF_MIN_TEMP,
                        default=const.DEFAULT_MIN_TEMP,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=40,
                            step=0.5,
                            unit_of_measurement=UnitOfTemperature.CELSIUS,
                        ),
                    ),
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Smart Cover Automation."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow.

        Avoid assigning to OptionsFlow.config_entry directly to prevent frame-helper
        warnings in tests; keep a private reference instead.
        """
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options for the integration."""
        if user_input is not None:
            # Persist options; Home Assistant will trigger entry update and reload
            return self.async_create_entry(title="Options", data=user_input)

        data = dict(self._config_entry.data)
        options = dict(self._config_entry.options or {})

        # Helper to read current option with fallback to data
        def opt(key: str, default: object | None = None) -> object | None:
            if key in options:
                return options[key]
            if key in data:
                return data[key]
            return default

        covers: list[str] = list(data.get(const.CONF_COVERS, []))

        # Build dynamic fields for per-cover directions as numeric azimuth angles (0-359)
        direction_fields: dict[vol.Marker, object] = {}
        for cover in covers:
            key = f"{cover}_cover_direction"
            # Compute default: accept numeric strings/floats; otherwise leave without default.
            raw = options.get(key, data.get(key))
            default_angle: float | None = None
            if isinstance(raw, str):
                # Try parse numeric string
                try:
                    default_angle = float(raw)
                except (TypeError, ValueError):
                    default_angle = None
            elif isinstance(raw, (int, float)):
                try:
                    default_angle = float(raw)
                except (TypeError, ValueError):
                    default_angle = None

            if default_angle is not None:
                direction_fields[vol.Optional(key, default=default_angle)] = (
                    selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=359, step=1, unit_of_measurement="°"
                        )
                    )
                )
            else:
                direction_fields[vol.Optional(key)] = selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=359, step=1, unit_of_measurement="°"
                    )
                )

        # Compute concrete defaults
        enabled_default = bool(opt(const.CONF_ENABLED, True))
        temp_sensor_default = str(opt(const.CONF_TEMP_SENSOR, "sensor.temperature"))
        raw_threshold = opt(
            const.CONF_SUN_ELEVATION_THRESHOLD, const.DEFAULT_SUN_ELEVATION_THRESHOLD
        )
        if isinstance(raw_threshold, (int, float, str)):
            try:
                threshold_default = float(raw_threshold)
            except (TypeError, ValueError):
                threshold_default = float(const.DEFAULT_SUN_ELEVATION_THRESHOLD)
        else:
            threshold_default = float(const.DEFAULT_SUN_ELEVATION_THRESHOLD)

        schema_dict: dict[vol.Marker, object] = {
            vol.Optional(
                const.CONF_ENABLED, default=enabled_default
            ): selector.BooleanSelector(),
            vol.Optional(
                const.CONF_TEMP_SENSOR,
                default=temp_sensor_default,
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                const.CONF_SUN_ELEVATION_THRESHOLD,
                default=threshold_default,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=90, step=1)
            ),
        }

        # Compute safe default for max_closure
        raw_max_closure = opt(const.CONF_MAX_CLOSURE, const.MAX_CLOSURE)
        if isinstance(raw_max_closure, (int, float, str)):
            try:
                max_closure_default = int(float(raw_max_closure))
            except (TypeError, ValueError):
                max_closure_default = int(const.MAX_CLOSURE)
        else:
            max_closure_default = int(const.MAX_CLOSURE)

        schema_dict[
            vol.Optional(const.CONF_MAX_CLOSURE, default=max_closure_default)
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0, max=100, step=1, unit_of_measurement="%"
            )
        )

        # Add dynamic direction fields at the end
        schema_dict.update(direction_fields)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
