"""Config flow for Smart Cover Automation integration."""

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
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
)


class FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for the integration."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            # Validate cover entities exist
            for cover in user_input[CONF_COVERS]:
                if not self.hass.states.async_available(cover):
                    errors["base"] = "invalid_cover"
                    break

            if not errors:
                # Create unique ID based on the covers being automated
                unique_id = "_".join(sorted(user_input[CONF_COVERS]))
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Cover Automation ({len(user_input[CONF_COVERS])} covers)",
                    data=user_input,
                )

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
