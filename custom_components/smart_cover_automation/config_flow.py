"""Config flow and options flow for Smart Cover Automation integration."""

from __future__ import annotations

from typing import Any, Mapping

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.helpers import selector

from . import const
from .config import ConfKeys, ResolvedConfig, resolve
from .util import to_float_or_none


#
# FlowHelper
#
class FlowHelper:
    """Helper class for config flow validation and schema building."""

    #
    # validate_user_input_step1
    #
    @staticmethod
    def validate_user_input_step1(hass: Any, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate step 1 input: covers and weather entity.

        Args:
            hass: Home Assistant instance
            user_input: User input from the form

        Returns:
            Dictionary of errors (empty if valid)
        """
        errors: dict[str, str] = {}

        # Validate covers
        covers = user_input.get(ConfKeys.COVERS.value, [])
        if not covers:
            errors[ConfKeys.COVERS.value] = const.ERROR_NO_COVERS
            const.LOGGER.error("No covers selected")
        elif hass:
            invalid_covers = []
            for cover in covers:
                state = hass.states.get(cover)
                if not state:
                    invalid_covers.append(cover)
                elif state.state == STATE_UNAVAILABLE:
                    const.LOGGER.warning(f"Cover {cover} is currently unavailable but will be configured")

            if invalid_covers:
                errors[ConfKeys.COVERS.value] = const.ERROR_INVALID_COVER
                const.LOGGER.error(f"Invalid covers selected: {invalid_covers}")

        # Validate weather entity
        weather_entity_id = user_input.get(ConfKeys.WEATHER_ENTITY_ID.value)
        if not weather_entity_id:
            errors[ConfKeys.WEATHER_ENTITY_ID.value] = const.ERROR_NO_WEATHER_ENTITY
            const.LOGGER.error("No weather entity selected")
        elif hass:
            weather_state = hass.states.get(weather_entity_id)
            if weather_state:
                supported_features = weather_state.attributes.get("supported_features", 0)
                if not supported_features & WeatherEntityFeature.FORECAST_DAILY:
                    errors[ConfKeys.WEATHER_ENTITY_ID.value] = const.ERROR_INVALID_WEATHER_ENTITY
                    const.LOGGER.error(f"Weather entity {weather_entity_id} does not support daily forecasts")
            else:
                errors[ConfKeys.WEATHER_ENTITY_ID.value] = const.ERROR_INVALID_WEATHER_ENTITY
                const.LOGGER.error(f"Weather entity {weather_entity_id} has no state value")

        return errors

    #
    # build_schema_step1
    #
    @staticmethod
    def build_schema_step1(resolved_settings: ResolvedConfig) -> vol.Schema:
        """Build schema for step 1: cover and weather selection.

        Args:
            resolved_settings: Resolved configuration with defaults

        Returns:
            Schema for step 1 form
        """
        schema_dict: dict[vol.Marker, object] = {}

        schema_dict[vol.Required(ConfKeys.WEATHER_ENTITY_ID.value, default=resolved_settings.weather_entity_id)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=Platform.WEATHER)
        )
        schema_dict[vol.Required(ConfKeys.COVERS.value, default=list(resolved_settings.covers))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=Platform.COVER, multiple=True)
        )

        return vol.Schema(schema_dict)

    #
    # build_schema_step2
    #
    @staticmethod
    def build_schema_step2(hass: Any, covers: list[str], defaults: Mapping[str, Any]) -> vol.Schema:
        """Build schema for step 2: azimuth configuration per cover.

        Args:
            hass: Home Assistant instance (for looking up cover friendly names)
            covers: List of cover entity IDs
            defaults: Dictionary to look up default azimuth values

        Returns:
            Schema for step 2 form
        """
        schema_dict: dict[vol.Marker, object] = {}

        for cover in sorted(covers):
            key = f"{cover}_{const.COVER_SFX_AZIMUTH}"
            raw = defaults.get(key)
            default_azimuth = to_float_or_none(raw)
            if default_azimuth is None:
                default_azimuth = 180

            azimuth_selector = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=359,
                    step=0.1,
                    unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )

            # Look up cover's friendly name
            cover_name = cover
            if hass:
                cover_state = hass.states.get(cover)
                if cover_state:
                    cover_name = cover_state.name

            description = {"key": const.COVER_AZIMUTH, "placeholder": {"cover_name": cover_name}}
            schema_dict[vol.Required(key, default=default_azimuth, description=description)] = azimuth_selector

        return vol.Schema(schema_dict)

    #
    # build_schema_step3
    #
    @staticmethod
    def build_schema_step3(resolved_settings: ResolvedConfig) -> vol.Schema:
        """Build schema for step 3: sun position, cover behavior, manual override.

        Args:
            resolved_settings: Resolved configuration with defaults

        Returns:
            Schema for step 3 form
        """
        duration_default = {
            "hours": resolved_settings.manual_override_duration // 3600,
            "minutes": (resolved_settings.manual_override_duration % 3600) // 60,
            "seconds": resolved_settings.manual_override_duration % 60,
        }

        return vol.Schema(
            {
                vol.Required(
                    ConfKeys.TEMP_THRESHOLD.value,
                    default=resolved_settings.temp_threshold,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°C",
                        min=10,
                        max=40,
                        step=0.5,
                    )
                ),
                vol.Required(
                    ConfKeys.SUN_ELEVATION_THRESHOLD.value,
                    default=resolved_settings.sun_elevation_threshold,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°",
                        min=-90,
                        max=90,
                    )
                ),
                vol.Required(
                    ConfKeys.SUN_AZIMUTH_TOLERANCE.value,
                    default=resolved_settings.sun_azimuth_tolerance,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="°",
                        min=0,
                        max=180,
                    )
                ),
                vol.Required(
                    ConfKeys.COVERS_MAX_CLOSURE.value,
                    default=resolved_settings.covers_max_closure,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="%",
                        min=0,
                        max=100,
                    )
                ),
                vol.Required(
                    ConfKeys.COVERS_MIN_CLOSURE.value,
                    default=resolved_settings.covers_min_closure,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="%",
                        min=0,
                        max=100,
                    )
                ),
                vol.Required(
                    ConfKeys.MANUAL_OVERRIDE_DURATION.value,
                    default=duration_default,
                ): selector.DurationSelector(selector.DurationSelectorConfig()),
            }
        )


#
# FlowHandler
#
class FlowHandler(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Config flow for the integration."""

    # Schema version
    # When changing the schema, increment the version and implement async_migrate_entry
    VERSION = 1
    # Explicit domain attribute for tests referencing FlowHandler.domain
    domain = const.DOMAIN

    #
    # async_step_user
    #
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle initial setup - create entry with empty config.

        User will configure the integration via options flow when ready.
        This provides a better UX by not overwhelming users during installation.
        """
        if user_input is None:
            # Show welcome message with no input fields
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
            )
        else:
            # User clicked submit - create entry with empty config
            return self.async_create_entry(
                title=const.INTEGRATION_NAME,
                data={},
            )

    #
    # async_get_options_flow
    #
    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


#
# OptionsFlowHandler
#
class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Smart Cover Automation."""

    #
    # __init__
    #
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow.

        Avoid assigning to OptionsFlow.config_entry directly to prevent frame-helper
        warnings in tests; keep a private reference instead.
        """
        self._config_entry = config_entry
        self._config_data: dict[str, Any] = {}

    #
    # async_step_init
    #
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 1: Cover and weather entity selection."""
        # Build defaults from existing config/options
        data = dict(self._config_entry.data) if self._config_entry.data else {}
        options = dict(self._config_entry.options) if self._config_entry.options else {}
        resolved_settings = resolve(options, data)

        if user_input is None:
            # Show the form
            return self.async_show_form(
                step_id="init",
                data_schema=FlowHelper.build_schema_step1(resolved_settings),
            )

        # Validate user input
        errors = FlowHelper.validate_user_input_step1(self.hass, user_input)
        if errors:
            # Show form again with errors
            return self.async_show_form(
                step_id="init",
                data_schema=FlowHelper.build_schema_step1(resolved_settings),
                errors=errors,
            )
        else:
            # Store step 1 data and proceed to step 2
            self._config_data.update(user_input)
            return await self.async_step_2()

    #
    # async_step_2
    #
    async def async_step_2(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 2: Configure azimuth for each cover."""
        # Get covers from accumulated config data
        covers = self._config_data.get(ConfKeys.COVERS.value, [])

        if user_input is None:
            # Build defaults from existing config/options (options takes precedence)
            data = dict(self._config_entry.data) if self._config_entry.data else {}
            options = dict(self._config_entry.options) if self._config_entry.options else {}
            defaults = {**data, **options}

            # Show the form
            return self.async_show_form(
                step_id="2",
                data_schema=FlowHelper.build_schema_step2(hass=self.hass, covers=covers, defaults=defaults),
            )
        else:
            # Store step 2 data and proceed to step 3
            self._config_data.update(user_input)
            return await self.async_step_3()

    #
    # async_step_3
    #
    async def async_step_3(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 3: Configure sun position, cover behavior, and manual override duration."""
        if user_input is None:
            # Build defaults from existing config/options (options takes precedence)
            data = dict(self._config_entry.data) if self._config_entry.data else {}
            options = dict(self._config_entry.options) if self._config_entry.options else {}
            defaults = {**data, **options}
            resolved_settings = resolve({}, defaults)

            # Show the form
            return self.async_show_form(
                step_id="3",
                data_schema=FlowHelper.build_schema_step3(resolved_settings),
            )

        # Store step 3 data
        self._config_data.update(user_input)

        # Build existing data and options
        data = dict(self._config_entry.data) if self._config_entry.data else {}
        options = dict(self._config_entry.options) if self._config_entry.options else {}
        combined = {**data, **options}

        # Update with new values from the flow
        combined.update(self._config_data)

        # Clean up orphaned cover settings from the combined data
        covers_in_input = self._config_data.get(ConfKeys.COVERS.value, [])
        keys_to_remove = []
        for key in combined.keys():
            if key.endswith(f"_{const.COVER_SFX_AZIMUTH}"):
                cover_entity = key.replace(f"_{const.COVER_SFX_AZIMUTH}", "")
                if cover_entity not in covers_in_input:
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            combined.pop(key, None)

        return self.async_create_entry(title="", data=combined)
