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


class ConfigFlowHelper:
    """Helper class for config flow validation and schema building."""

    @staticmethod
    def validate_user_input_step1(hass: Any, user_input: dict[str, Any]) -> dict[str, str]:
        """Validate step 1 (user/init) input: covers and weather entity.

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


class FlowHandler(config_entries.ConfigFlow, domain=const.DOMAIN):
    """Config flow for the integration."""

    # Schema version
    # When changing the schema, increment the version and implement async_migrate_entry
    VERSION = 1
    # Explicit domain attribute for tests referencing FlowHandler.domain
    domain = const.DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._config_data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 1: Cover and weather entity selection.

        HA calls async_step_user(None) to show the menu on first entry, then calls it again with a dict after submit.
        """
        # Show menu on first call (before any user interaction)
        if user_input is None and not self._config_data and not hasattr(self, "_menu_shown"):
            self._menu_shown = True
            return self.async_show_menu(
                step_id="user",
                menu_options=["user_form", "2", "3"],
            )

        # Build defaults from current config data
        resolved_settings = resolve({}, self._config_data)

        if user_input is not None:
            # Validate covers and weather entity
            errors = ConfigFlowHelper.validate_user_input_step1(self.hass, user_input)

            if errors:
                # Show form again with errors
                return self.async_show_form(
                    step_id="user_form",
                    data_schema=ConfigFlowHelper.build_schema_step1(resolved_settings),
                    errors=errors,
                )

            # Store step 1 data and proceed to azimuth configuration
            self._config_data.update(user_input)
            return await self.async_step_2()

        # Show the form
        return self.async_show_form(
            step_id="user_form",
            data_schema=ConfigFlowHelper.build_schema_step1(resolved_settings),
        )

    async def async_step_user_form(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle user form step (called from menu)."""
        return await self.async_step_user(user_input)

    async def async_step_2(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 2: Configure azimuth for each cover."""
        # Get covers from accumulated config data
        covers: list[str] = self._config_data.get(ConfKeys.COVERS.value, [])

        if user_input is not None:
            # Store step 2 data and show menu
            self._config_data.update(user_input)
            return self.async_show_menu(
                step_id="user",
                menu_options=["user_form", "2", "3"],
            )

        # Show azimuth configuration form
        return self.async_show_form(
            step_id="2",
            data_schema=ConfigFlowHelper.build_schema_step2(hass=self.hass, covers=covers, defaults=self._config_data),
        )

    async def async_step_3(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 3: Configure sun position, cover behavior, and manual override duration."""
        if user_input is not None:
            # Store step 3 data and show menu with submit option
            self._config_data.update(user_input)
            return self.async_show_menu(
                step_id="user",
                menu_options=["user_form", "2", "3", "submit"],
            )

        # Build defaults from accumulated config data
        data = dict(self._config_data)
        resolved_settings = resolve({}, data)

        # Show final settings form
        return self.async_show_form(
            step_id="3",
            data_schema=ConfigFlowHelper.build_schema_step3(resolved_settings),
        )

    async def async_step_submit(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Submit the configuration."""
        return self.async_create_entry(
            title=const.INTEGRATION_NAME,
            data=dict(self._config_data),
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Smart Cover Automation."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow.

        Avoid assigning to OptionsFlow.config_entry directly to prevent frame-helper
        warnings in tests; keep a private reference instead.
        """
        self._config_entry = config_entry
        self._config_data: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 1: Cover and weather entity selection.

        HA calls async_step_init(None) to show the menu on first entry, then calls it again with a dict after submit.
        """
        # Show menu on first call (before any user interaction)
        if user_input is None and not self._config_data and not hasattr(self, "_menu_shown"):
            self._menu_shown = True
            return self.async_show_menu(
                step_id="init",
                menu_options=["init_form", "2", "3"],
            )

        # Build defaults from existing config/options
        data = dict(self._config_entry.data) if self._config_entry.data else {}
        options = dict(self._config_entry.options) if self._config_entry.options else {}
        resolved_settings = resolve(options, data)

        if user_input is not None:
            # Validate covers and weather entity
            errors = ConfigFlowHelper.validate_user_input_step1(self.hass, user_input)

            if errors:
                # Show form again with errors
                return self.async_show_form(
                    step_id="init_form",
                    data_schema=ConfigFlowHelper.build_schema_step1(resolved_settings),
                    errors=errors,
                )

            # Store step 1 data and proceed to azimuth configuration
            self._config_data.update(user_input)
            return await self.async_step_2()

        # Show the form
        return self.async_show_form(
            step_id="init_form",
            data_schema=ConfigFlowHelper.build_schema_step1(resolved_settings),
        )

    async def async_step_init_form(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Handle init form step (called from menu)."""
        return await self.async_step_init(user_input)

    async def async_step_2(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 2: Configure azimuth for each cover."""
        # Get covers from accumulated config data, or fall back to existing config/options
        covers: list[str] = self._config_data.get(ConfKeys.COVERS.value, [])
        if not covers:
            # If no covers in accumulated data, get from existing config/options
            data = dict(self._config_entry.data) if self._config_entry.data else {}
            options = dict(self._config_entry.options) if self._config_entry.options else {}
            combined = {**data, **options}
            covers = combined.get(ConfKeys.COVERS.value, [])

        if user_input is not None:
            # Store step 2 data and show menu
            self._config_data.update(user_input)
            return self.async_show_menu(
                step_id="init",
                menu_options=["init_form", "2", "3"],
            )

        # Build defaults from existing config/options (options takes precedence)
        data = dict(self._config_entry.data) if self._config_entry.data else {}
        options = dict(self._config_entry.options) if self._config_entry.options else {}
        defaults = {**data, **options}

        # Show azimuth configuration form
        return self.async_show_form(
            step_id="2",
            data_schema=ConfigFlowHelper.build_schema_step2(hass=self.hass, covers=covers, defaults=defaults),
        )

    async def async_step_3(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 3: Configure sun position, cover behavior, and manual override duration."""
        if user_input is not None:
            # Store step 3 data
            self._config_data.update(user_input)

            # Clean up orphaned cover settings
            covers_in_input = self._config_data.get(ConfKeys.COVERS.value, [])
            keys_to_remove = []
            for key in self._config_data.keys():
                if key.endswith(f"_{const.COVER_SFX_AZIMUTH}"):
                    cover_entity = key.replace(f"_{const.COVER_SFX_AZIMUTH}", "")
                    if cover_entity not in covers_in_input:
                        keys_to_remove.append(key)

            for key in keys_to_remove:
                self._config_data.pop(key, None)

            # Show menu with submit option
            return self.async_show_menu(
                step_id="init",
                menu_options=["init_form", "2", "3", "submit"],
            )

        # Build defaults from existing config/options (options takes precedence)
        data = dict(self._config_entry.data) if self._config_entry.data else {}
        options = dict(self._config_entry.options) if self._config_entry.options else {}
        defaults = {**data, **options}
        resolved_settings = resolve({}, defaults)

        # Show final settings form
        return self.async_show_form(
            step_id="3",
            data_schema=ConfigFlowHelper.build_schema_step3(resolved_settings),
        )

    async def async_step_submit(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Submit the configuration."""
        return self.async_create_entry(title="", data=self._config_data)
