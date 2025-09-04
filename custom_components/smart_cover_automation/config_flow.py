"""Config flow and options flow for Smart Cover Automation integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import selector

from .const import (
    AUTOMATION_TYPE_TEMPERATURE,
    AUTOMATION_TYPES,
    CONF_AUTOMATION_TYPE,
    CONF_COVERS,
    CONF_ENABLED,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SUN_ELEVATION_THRESHOLD,
    CONF_TEMP_SENSOR,
    COVER_DIRECTIONS,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_SUN_ELEVATION_THRESHOLD,
    DOMAIN,
    LOGGER,
)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the integration."""

    VERSION = 1
    # Provide explicit domain attribute for tests referencing FlowHandler.domain
    domain = DOMAIN

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
                for cover in user_input[CONF_COVERS]:
                    state = self.hass.states.get(cover)
                    if not state:
                        invalid_covers.append(cover)
                    elif state.state == "unavailable":
                        LOGGER.warning(
                            "Cover %s is currently unavailable but will be configured",
                            cover,
                        )

                if invalid_covers:
                    errors["base"] = "invalid_cover"
                    LOGGER.error(
                        "Invalid covers selected: %s",
                        invalid_covers,
                    )

                # Validate temperature ranges if temperature automation
                if (
                    user_input[CONF_AUTOMATION_TYPE] == AUTOMATION_TYPE_TEMPERATURE
                    and CONF_MAX_TEMP in user_input
                    and CONF_MIN_TEMP in user_input
                ):
                    max_temp = user_input[CONF_MAX_TEMP]
                    min_temp = user_input[CONF_MIN_TEMP]
                    if max_temp <= min_temp:
                        errors["base"] = "invalid_temperature_range"
                        LOGGER.error(
                            "Invalid temperature range: max=%s <= min=%s",
                            max_temp,
                            min_temp,
                        )

                if not errors:
                    # Create unique ID based on the covers being automated
                    unique_id = "_".join(sorted(user_input[CONF_COVERS]))
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=(
                            f"Cover Automation ({len(user_input[CONF_COVERS])} covers)"
                        ),
                        data=user_input,
                    )

            except (KeyError, ValueError, TypeError) as err:
                LOGGER.exception("Configuration validation error: %s", err)
                errors["base"] = "invalid_config"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_COVERS): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="cover",
                            multiple=True,
                        ),
                    ),
                    vol.Required(
                        CONF_AUTOMATION_TYPE,
                        default=AUTOMATION_TYPE_TEMPERATURE,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=AUTOMATION_TYPES,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Optional(
                        CONF_MAX_TEMP,
                        default=DEFAULT_MAX_TEMP,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=40,
                            step=0.5,
                            unit_of_measurement=UnitOfTemperature.CELSIUS,
                        ),
                    ),
                    vol.Optional(
                        CONF_MIN_TEMP,
                        default=DEFAULT_MIN_TEMP,
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
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options for the integration."""
        if user_input is not None:
            # Persist options; Home Assistant will trigger entry update and reload
            return self.async_create_entry(title="Options", data=user_input)

        data = dict(self.config_entry.data)
        options = dict(self.config_entry.options or {})

        # Helper to read current option with fallback to data
        def opt(key: str, default: object | None = None) -> object | None:
            if key in options:
                return options[key]
            if key in data:
                return data[key]
            return default

        covers: list[str] = list(data.get(CONF_COVERS, []))

        # Build dynamic fields for per-cover directions
        direction_fields: dict[vol.Marker, object] = {}
        for cover in covers:
            key = f"{cover}_cover_direction"
            direction_fields[vol.Optional(key)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=COVER_DIRECTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )

        # Compute concrete defaults
        enabled_default = bool(opt(CONF_ENABLED, True))
        temp_sensor_default = str(opt(CONF_TEMP_SENSOR, "sensor.temperature"))
        raw_threshold = opt(
            CONF_SUN_ELEVATION_THRESHOLD, DEFAULT_SUN_ELEVATION_THRESHOLD
        )
        if isinstance(raw_threshold, (int, float, str)):
            try:
                threshold_default = float(raw_threshold)
            except (TypeError, ValueError):
                threshold_default = float(DEFAULT_SUN_ELEVATION_THRESHOLD)
        else:
            threshold_default = float(DEFAULT_SUN_ELEVATION_THRESHOLD)

        schema_dict: dict[vol.Marker, object] = {
            vol.Optional(
                CONF_ENABLED, default=enabled_default
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_TEMP_SENSOR,
                default=temp_sensor_default,
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_SUN_ELEVATION_THRESHOLD,
                default=threshold_default,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=90, step=1)
            ),
        }

        # Add dynamic direction fields at the end
        schema_dict.update(direction_fields)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )
