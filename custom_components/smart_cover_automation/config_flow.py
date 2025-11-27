"""Config flow and options flow for Smart Cover Automation integration."""

from __future__ import annotations

from typing import Any, Mapping

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

from . import const
from .config import ConfKeys, ResolvedConfig, resolve
from .util import to_float_or_none, to_int_or_none


#
# FlowHelper
#
class FlowHelper:
    """Helper class for config flow validation and schema building."""

    #
    # validate_user_input_step_1
    #
    @staticmethod
    def validate_user_input_step_1(hass: Any, user_input: dict[str, Any]) -> dict[str, str]:
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
    # build_schema_step_1
    #
    @staticmethod
    def build_schema_step_1(resolved_settings: ResolvedConfig) -> vol.Schema:
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
    # build_schema_step_2
    #
    @staticmethod
    def build_schema_step_2(covers: list[str], defaults: Mapping[str, Any]) -> vol.Schema:
        """Build schema for step 2: azimuth configuration per cover.

        Args:
            covers: List of cover entity IDs
            defaults: Dictionary to look up default values

        Returns:
            Schema for step 2 form
        """
        schema_dict: dict[vol.Marker, object] = {}

        for cover in sorted(covers):
            # Build a key for storage
            key = f"{cover}_{const.COVER_SFX_AZIMUTH}"

            # Get the default value
            raw = defaults.get(key)
            default_value = to_float_or_none(raw)
            if default_value is None:
                default_value = 180

            # Configure a selector
            value_selector = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=359,
                    step=0.1,
                    unit_of_measurement="°",
                    mode=selector.NumberSelectorMode.BOX,
                )
            )

            schema_dict[vol.Required(key, default=default_value)] = value_selector

        return vol.Schema(schema_dict)

    #
    # build_schema_step_3
    #
    @staticmethod
    def build_schema_step_3(resolved_settings: ResolvedConfig) -> vol.Schema:
        """Build schema for step 3: sun position, cover behavior, manual override.

        Args:
            resolved_settings: Resolved configuration with defaults

        Returns:
            Schema for step 3 form
        """
        return vol.Schema({})

    #
    # build_schema_step_4
    #
    @staticmethod
    def build_schema_step_4(covers: list[str], defaults: Mapping[str, Any]) -> vol.Schema:
        """Build schema for step 4: min/max position per cover.

        Args:
            covers: List of cover entity IDs
            defaults: Dictionary to look up default values

        Returns:
            Schema for step 4 form
        """

        schema_dict: dict[vol.Marker, object] = {}

        # Build schema dict for min closure positions and group inside collapsible section
        min_schema_dict = FlowHelper._build_schema_cover_positions(covers, const.COVER_SFX_MIN_CLOSURE, defaults)
        if min_schema_dict:
            schema_dict[vol.Optional(const.STEP_4_SECTION_MIN_CLOSURE)] = section(
                vol.Schema(min_schema_dict),
                {"collapsed": True},
            )

        # Build schema dict for max closure positions and group inside collapsible section
        max_schema_dict = FlowHelper._build_schema_cover_positions(covers, const.COVER_SFX_MAX_CLOSURE, defaults)
        if max_schema_dict:
            schema_dict[vol.Optional(const.STEP_4_SECTION_MAX_CLOSURE)] = section(
                vol.Schema(max_schema_dict),
                {"collapsed": True},
            )

        return vol.Schema(schema_dict)

    #
    # _build_schema_cover_positions
    #
    @staticmethod
    def _build_schema_cover_positions(covers: list[str], suffix: str, defaults: Mapping[str, Any]) -> dict[vol.Marker, object]:
        """Helper to build schema for per-cover position suffix (min or max closure).

        Args:
            covers: List of cover entity IDs
            suffix: Suffix to append to each cover entity ID for the key
            defaults: Dictionary to look up default values
        """

        schema_dict: dict[vol.Marker, object] = {}

        for cover in sorted(covers):
            # Build a key for storage
            key = f"{cover}_{suffix}"

            # Get the default value
            raw = defaults.get(key)
            default_value = to_int_or_none(raw)

            # Text selector (number input) allows clearing the field entirely
            value_selector = selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.NUMBER,
                    suffix="%",
                )
            )

            # Use suggested value instead of setting a default to allow clearing the field
            if default_value is not None:
                key_marker = vol.Optional(key, description={"suggested_value": str(default_value)})
            else:
                key_marker = vol.Optional(key)

            schema_dict[key_marker] = value_selector

        return schema_dict

    #
    # build_schema_step_5
    #
    @staticmethod
    def build_schema_step_5(covers: list[str], defaults: Mapping[str, Any]) -> vol.Schema:
        """Build schema for step 5: window sensors per cover.

        Args:
            covers: List of cover entity IDs
            defaults: Dictionary to look up default values

        Returns:
            Schema for step 5 form
        """

        schema_dict: dict[vol.Marker, object] = {}

        # Build schema dict for window sensors and group inside collapsible section
        window_sensors_schema_dict = FlowHelper._build_schema_cover_entities(covers, const.COVER_SFX_WINDOW_SENSORS, defaults)
        if window_sensors_schema_dict:
            schema_dict[vol.Optional(const.STEP_5_SECTION_WINDOW_SENSORS)] = section(
                vol.Schema(window_sensors_schema_dict),
                {"collapsed": True},
            )

        return vol.Schema(schema_dict)

    #
    # _build_schema_cover_entities
    #
    @staticmethod
    def _build_schema_cover_entities(covers: list[str], suffix: str, defaults: Mapping[str, Any]) -> dict[vol.Marker, object]:
        """Helper to build schema for per-cover entity selection (e.g., associated window sensors).

        Args:
            covers: List of cover entity IDs
            suffix: Suffix to append to each cover entity ID for the key
            defaults: Dictionary to look up default values
        """

        schema_dict: dict[vol.Marker, object] = {}

        for cover in sorted(covers):
            # Build a key for storage
            key = f"{cover}_{suffix}"

            # Get the default value
            raw = defaults.get(key)
            default_value = raw if isinstance(raw, list) else []

            # Entity selector for multiple binary sensors
            value_selector = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=Platform.BINARY_SENSOR,
                    multiple=True,
                )
            )

            # Use default value for entity selector
            key_marker = vol.Optional(key, default=default_value)

            schema_dict[key_marker] = value_selector

        return schema_dict

    #
    # build_schema_step_6
    #
    @staticmethod
    def build_schema_step_6(covers: list[str], resolved_settings: ResolvedConfig) -> vol.Schema:
        """Build schema for step 6 settings.

        Args:
            covers: List of cover entity IDs
            resolved_settings: Resolved configuration with defaults

        Returns:
            Schema for step 6 form
        """

        schema_dict: dict[vol.Marker, object] = {}

        # "Disable cover opening at night" (above the section)
        schema_dict[
            vol.Required(
                ConfKeys.NIGHTTIME_BLOCK_OPENING.value,
                default=resolved_settings.nighttime_block_opening,
            )
        ] = selector.BooleanSelector()

        #
        # Section: Disable automation in time range
        #
        time_range_schema_dict: dict[vol.Marker, object] = {}

        # Setting to enable/disable
        time_range_schema_dict[
            vol.Required(
                ConfKeys.AUTOMATION_DISABLED_TIME_RANGE.value,
                default=resolved_settings.automation_disabled_time_range,
            )
        ] = selector.BooleanSelector()

        # Start time for disabling the automation
        time_range_schema_dict[
            vol.Required(
                ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START.value,
                default=resolved_settings.automation_disabled_time_range_start,
            )
        ] = selector.TimeSelector()

        # End time for disabling the automation
        time_range_schema_dict[
            vol.Required(
                ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END.value,
                default=resolved_settings.automation_disabled_time_range_end,
            )
        ] = selector.TimeSelector()

        # Group settings in collapsed section
        schema_dict[vol.Optional(const.STEP_6_SECTION_TIME_RANGE)] = section(
            vol.Schema(time_range_schema_dict),
            {"collapsed": True},
        )

        #
        # Section: Close covers after sunset
        #
        covers_sunset_schema_dict: dict[vol.Marker, object] = {}

        # Setting to enable/disable
        covers_sunset_schema_dict[
            vol.Required(
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET.value,
                default=resolved_settings.close_covers_after_sunset,
            )
        ] = selector.BooleanSelector()

        delay_default = {
            "hours": resolved_settings.close_covers_after_sunset_delay // 3600,
            "minutes": (resolved_settings.close_covers_after_sunset_delay % 3600) // 60,
            "seconds": resolved_settings.close_covers_after_sunset_delay % 60,
        }

        # Close covers after sunset: delay
        covers_sunset_schema_dict[
            vol.Required(
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_DELAY.value,
                default=delay_default,
            )
        ] = selector.DurationSelector()

        # Close covers after sunset: cover list
        covers_sunset_schema_dict[
            vol.Required(
                ConfKeys.CLOSE_COVERS_AFTER_SUNSET_COVER_LIST.value,
                default=list(resolved_settings.close_covers_after_sunset_cover_list),
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=Platform.COVER,
                multiple=True,
                include_entities=covers,
            )
        )

        # Group settings in collapsed section
        schema_dict[vol.Optional(const.STEP_6_SECTION_CLOSE_AFTER_SUNSET)] = section(
            vol.Schema(covers_sunset_schema_dict),
            {"collapsed": True},
        )

        return vol.Schema(schema_dict)

    #
    # extract_from_section_input
    #
    @staticmethod
    def extract_from_section_input(user_input: Mapping[str, Any], section_names: set[str]) -> tuple[dict[str, Any], set[str]]:
        """Flatten two-level input from sections into a one-level dict.

        Returns a tuple of (flattened_dict, sections_present) where sections_present
        is a set of section names that were in the input.

        A section is in the input if:
          1) the user changed one or more of its fields, or
          2) at least one field has a value
        Only the fields with values are included in the dictionary, e.g.:
          'section_max_closure': {'cover.kitchen_cover_max_closure': '20'}
        If the user cleared all fields of a section, an empty dictionary is returned, e.g.:
          'section_min_closure': {}

        Args:
            user_input: Raw user input from the form
            section_names: Set of section names to extract

        Returns:
            Tuple of (flattened_dict, sections_present)
        """

        flattened: dict[str, Any] = {}
        sections_present: set[str] = set()

        for key, value in user_input.items():
            if key in section_names:
                # We found a section
                sections_present.add(key)
                if isinstance(value, Mapping):
                    # The section has values
                    flattened.update(value)
                elif value in (None, vol.UNDEFINED):
                    # Empty section
                    continue
                else:
                    # We have a non-mapping value in a section (should not happen), store as-is
                    flattened[key] = value
            else:
                # Regular key-value pair
                flattened[key] = value

        return flattened, sections_present


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
    # _is_empty_value
    #
    @staticmethod
    def _is_empty_value(value: Any) -> bool:
        """Check if a value represents a cleared/empty field."""
        return value in (None, "") or value is vol.UNDEFINED

    #
    # _to_int
    #
    @staticmethod
    def _to_int(value: Any) -> int | None:
        """Convert a value to int, treating cleared values as None."""
        if OptionsFlowHandler._is_empty_value(value):
            return None
        return to_int_or_none(value)

    #
    # _build_section_cover_settings
    #
    @staticmethod
    def _build_section_cover_settings(
        user_input: dict[str, Any],
        section_name: str,
        suffix: str,
        covers: list[str],
        current_settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a dict with per-cover settings for a section.

        If a section is not present in the input, returns an empty dict.
        If a section is present, includes settings for ALL covers, with values being:
        - The user-entered value (or None if cleared), OR
        - The existing value if the field wasn't in the form

        Args:
            user_input: Raw user input from the form (may contain sections)
            section_name: Name of the section to extract
            suffix: Suffix for the per-cover keys
            covers: List of cover entity IDs
            current_settings: Current configuration settings

        Returns:
            Dictionary with normalized per-cover settings for this section
        """
        # Determine which section names are possible based on the suffix
        if suffix in (const.COVER_SFX_MIN_CLOSURE, const.COVER_SFX_MAX_CLOSURE):
            section_names = {const.STEP_4_SECTION_MIN_CLOSURE, const.STEP_4_SECTION_MAX_CLOSURE}
        elif suffix == const.COVER_SFX_WINDOW_SENSORS:
            section_names = {const.STEP_5_SECTION_WINDOW_SENSORS}
        else:
            # If you add a new per-cover section, update this method
            raise AssertionError(f"Unknown suffix '{suffix}' in _build_section_cover_settings")

        # Extract cover data and determine which sections are present
        user_input_extracted, sections_present = FlowHelper.extract_from_section_input(user_input, section_names)

        result: dict[str, Any] = {}
        if section_name not in sections_present:
            return result

        # When a section is present, we need to distinguish between:
        # 1. Fields that were actually modified by the user
        # 2. Fields that have default/empty values (should be ignored)
        # 3. Fields that were explicitly cleared (had value, now cleared)

        for cover in covers:
            key = f"{cover}_{suffix}"
            current_value = current_settings.get(key)

            if key in user_input_extracted:
                # We have the field in the input, convert it based on suffix type
                if suffix == const.COVER_SFX_WINDOW_SENSORS:
                    # Window sensors are lists - keep as-is
                    new_value = user_input_extracted[key]
                else:
                    # Min/max closures are integers (or None if cleared)
                    new_value = OptionsFlowHandler._to_int(user_input_extracted[key])

                # Only include if the value actually changed or is being explicitly cleared
                # For window sensors, empty list [] is a default/no-op if there was no previous value
                if suffix == const.COVER_SFX_WINDOW_SENSORS:
                    # Include if: value changed, OR user is clearing an existing config
                    if new_value != current_value and not (new_value == [] and current_value is None):
                        result[key] = new_value
                else:
                    # For min/max closure, include if value changed
                    if new_value != current_value:
                        result[key] = new_value
            else:
                # Field not in form submission
                # If the extracted dict is empty, the user cleared all fields → set to None
                if not user_input_extracted and current_value is not None:
                    # Only record explicit clearing if there was a previous value
                    result[key] = None
        return result

    #
    # _current_settings
    #
    def _current_settings(self) -> dict[str, Any]:
        """Get current settings from options storage.

        Returns:
            Dictionary of current option values
        """
        return dict(self._config_entry.options) if self._config_entry.options else {}

    #
    # _get_covers
    #
    def _get_covers(self) -> list[str]:
        """Get the list of selected covers from flow data or current settings.

        The flow data only contains changed values; if the covers were not changed
        in this options flow session, fall back to the existing settings.
        """
        covers: list[str] = self._config_data.get(ConfKeys.COVERS.value) or self._current_settings().get(ConfKeys.COVERS.value, [])
        return covers

    #
    # _finalize_and_save
    #
    def _finalize_and_save(self) -> config_entries.ConfigFlowResult:
        """Finalize configuration by merging, cleaning up, and saving.

        This method:
        1. Merges current settings with new input from the flow
        2. Removes orphaned per-cover settings for covers no longer selected
        3. Removes keys with empty/cleared values
        4. Saves the configuration and triggers integration reload

        Returns:
            ConfigFlowResult to complete the options flow
        """

        # Get the selected covers
        covers_in_input = self._get_covers()

        # Combine current settings with new input from the options flow (the latter taking precedence)
        current = self._current_settings()
        merged = {**current, **self._config_data}

        # Log changed, new, and removed settings
        changed_settings = {}
        new_settings = {}
        for key, new_value in merged.items():
            old_value = current.get(key)
            if key not in current:
                new_settings[key] = new_value
            elif old_value != new_value:
                changed_settings[key] = {"old": old_value, "new": new_value}

        removed_settings = {}
        for key, old_value in current.items():
            # Check if key had a value before but is now None
            if key in merged and merged[key] is None and old_value is not None:
                removed_settings[key] = old_value

        if changed_settings:
            const.LOGGER.info(f"Options flow: {len(changed_settings)} changed settings: {changed_settings}")
        else:
            const.LOGGER.info("Options flow: No changed settings")
        if new_settings:
            const.LOGGER.info(f"Options flow: {len(new_settings)} new settings: {new_settings}")
        else:
            const.LOGGER.info("Options flow: No new settings")
        if removed_settings:
            const.LOGGER.info(f"Options flow: {len(removed_settings)} removed settings: {removed_settings}")
        else:
            const.LOGGER.info("Options flow: No removed settings")

        # Clean up orphaned cover settings and empty values from the merged data
        keys_to_remove = []
        suffixes = (
            f"_{const.COVER_SFX_AZIMUTH}",
            f"_{const.COVER_SFX_MAX_CLOSURE}",
            f"_{const.COVER_SFX_MIN_CLOSURE}",
            f"_{const.COVER_SFX_WINDOW_SENSORS}",
        )
        for key, value in list(merged.items()):
            # Remove keys with empty values
            if self._is_empty_value(value):
                keys_to_remove.append(key)
                continue

            # Remove per-cover settings (from later steps) for covers no longer selected (in step 1)
            for suffix in suffixes:
                if key.endswith(suffix):
                    cover_entity = key[: -len(suffix)]
                    if cover_entity not in covers_in_input:
                        keys_to_remove.append(key)
                    break

        # Now remove the keys identified as superfluous
        for key in keys_to_remove:
            merged.pop(key, None)

        const.LOGGER.debug(f"Options flow completed. Final configuration being saved: {merged}")

        # Apply the new settings
        # This triggers a reload of the integration with the updated configuration.
        # The reload is required to apply the changes to the coordinator.
        return self.async_create_entry(title="", data=merged)

    #
    # async_step_init
    #
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 1: Cover and weather entity selection."""

        # Get currently valid settings
        current_settings = self._current_settings()
        # Fill in defaults where there's no existing value
        resolved_settings = resolve(current_settings)

        if user_input is None:
            # Show the form
            return self.async_show_form(
                step_id="init",
                data_schema=FlowHelper.build_schema_step_1(resolved_settings),
            )
        else:
            # Validate user input
            errors = FlowHelper.validate_user_input_step_1(self.hass, user_input)
            if errors:
                # Convert user input into resolved settings
                resolved_settings = resolve(user_input)
                # Show form again with errors
                return self.async_show_form(
                    step_id="init",
                    data_schema=FlowHelper.build_schema_step_1(resolved_settings),
                    errors=errors,
                )
            else:
                const.LOGGER.debug(f"Options flow step 1 user input: {user_input}")

                # Store step 1 data (temporarily, for the next step of the flow) and proceed to step 2
                self._config_data.update(user_input)
                return await self.async_step_2()

    #
    # async_step_2
    #
    async def async_step_2(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 2: Configure azimuth for each cover."""

        if user_input is None:
            # Get currently valid settings
            current_settings = self._current_settings()

            # Get the selected covers
            selected_covers = self._get_covers()

            # Show the form
            return self.async_show_form(
                step_id="2",
                data_schema=FlowHelper.build_schema_step_2(covers=selected_covers, defaults=current_settings),
            )
        else:
            const.LOGGER.debug(f"Options flow step 2 user input: {user_input}")

            # Store step 2 data (temporarily, for the next step of the flow) and proceed to step 3
            self._config_data.update(user_input)
            return await self.async_step_3()

    #
    # async_step_3
    #
    async def async_step_3(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 3: Configure sun position, cover behavior, and manual override duration."""

        if user_input is None:
            # Get currently valid settings
            current_settings = self._current_settings()
            # Fill in defaults where there's no existing value
            resolved_settings = resolve(current_settings)

            # Show the form
            return self.async_show_form(
                step_id="3",
                data_schema=FlowHelper.build_schema_step_3(resolved_settings),
            )
        else:
            const.LOGGER.debug(f"Options flow step 3 user input: {user_input}")

            # Store step 3 data (temporarily, for the next step of the flow) and proceed to step 4
            self._config_data.update(user_input)
            return await self.async_step_4()

    #
    # async_step_4
    #
    async def async_step_4(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 4: Configure max/min position for each cover."""

        if user_input is None:
            # Get currently valid settings
            current_settings = self._current_settings()

            # Get the selected covers
            selected_covers = self._get_covers()

            # Show the form
            return self.async_show_form(
                step_id="4",
                data_schema=FlowHelper.build_schema_step_4(covers=selected_covers, defaults=current_settings),
            )

        const.LOGGER.debug(f"Options flow step 4 user input: {user_input}")

        # Get the selected covers
        covers_in_input = self._get_covers()

        # Get currently valid settings
        current_settings = self._current_settings()

        # Build complete lists of min and max closure settings for all covers
        min_closure_data = self._build_section_cover_settings(
            user_input, const.STEP_4_SECTION_MIN_CLOSURE, const.COVER_SFX_MIN_CLOSURE, covers_in_input, current_settings
        )
        max_closure_data = self._build_section_cover_settings(
            user_input, const.STEP_4_SECTION_MAX_CLOSURE, const.COVER_SFX_MAX_CLOSURE, covers_in_input, current_settings
        )

        # Store the complete min and max per-cover settings
        self._config_data.update(min_closure_data)
        self._config_data.update(max_closure_data)

        # Proceed to step 5
        return await self.async_step_5()

    #
    # async_step_5
    #
    async def async_step_5(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 5: Configure window sensors for each cover."""

        if user_input is None:
            # Get currently valid settings
            current_settings = self._current_settings()

            # Get the selected covers
            selected_covers = self._get_covers()

            # Show the form
            return self.async_show_form(
                step_id="5",
                data_schema=FlowHelper.build_schema_step_5(covers=selected_covers, defaults=current_settings),
            )

        const.LOGGER.debug(f"Options flow step 5 user input: {user_input}")

        # Get the selected covers
        covers_in_input = self._get_covers()

        # Get currently valid settings
        current_settings = self._current_settings()

        # Build complete lists of window sensor settings for all covers
        window_sensor_data = self._build_section_cover_settings(
            user_input, const.STEP_5_SECTION_WINDOW_SENSORS, const.COVER_SFX_WINDOW_SENSORS, covers_in_input, current_settings
        )

        # Store the complete per-cover settings
        self._config_data.update(window_sensor_data)

        # Proceed to step 5
        return await self.async_step_6()

    #
    # async_step_6
    #
    async def async_step_6(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Step 6: Configure evening closure and night silence settings."""

        if user_input is None:
            # Get currently valid settings
            current_settings = self._current_settings()
            # Fill in defaults where there's no existing value
            resolved_settings = resolve(current_settings)

            # Get the selected covers
            selected_covers = self._get_covers()

            # Show the form
            return self.async_show_form(
                step_id="6",
                data_schema=FlowHelper.build_schema_step_6(covers=selected_covers, resolved_settings=resolved_settings),
            )

        const.LOGGER.debug(f"Options flow step 6 user input: {user_input}")

        # Extract section data if present
        section_names = {const.STEP_6_SECTION_TIME_RANGE, const.STEP_6_SECTION_CLOSE_AFTER_SUNSET}
        user_input_extracted, sections_present = FlowHelper.extract_from_section_input(user_input, section_names)

        # Store step 6 data (use extracted data to handle sections properly)
        self._config_data.update(user_input_extracted)

        # Finalize and save configuration
        return self._finalize_and_save()
