"""
Constants for smart_cover_automation.

Logging Information:
- INFO includes automation decisions and cover actions
- Set log level to WARNING for configuration issues
- Set log level to ERROR for system failures

Note: Detailed cover position/evaluation calculations are not logged by default.

To enable verbose logging, either use the integration's Options (Verbose logging)
or add this to your configuration.yaml:
logger:
  logs:
    custom_components.smart_cover_automation: debug
"""

from __future__ import annotations

from datetime import timedelta
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Final

# For static type checking only
if TYPE_CHECKING:
    from .log import Log

# Module-level logger for the integration.
# This is an instance of the custom Log class which wraps Python's standard logger.
# Without an entry_id, log messages have no prefix.
# With an entry_id, messages are prefixed with [xxxxx] to identify the instance.
#
# Note: Imported lazily to avoid circular imports.
#       Instantiated at module load time by _init_logger().
LOGGER: Log


#
# _init_logger
#
def _init_logger() -> None:
    """Initialize the module-level LOGGER. Called once at module load time."""

    global LOGGER  # noqa: PLW0603
    try:
        from .log import Log

        LOGGER = Log()
    except ImportError:
        # Fallback for when module is loaded outside package context (e.g., CI tests)
        # Import log.py directly to avoid triggering __init__.py which needs homeassistant
        import importlib.util
        from pathlib import Path

        log_path = Path(__file__).parent / "log.py"
        spec = importlib.util.spec_from_file_location("log", log_path)
        if spec and spec.loader:
            log_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(log_module)
            LOGGER = log_module.Log()
        else:
            raise ImportError("Could not load log.py")


#
# LogSeverity
#
class LogSeverity(Enum):
    """Log severity levels for structured logging."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


DOMAIN: Final[str] = "smart_cover_automation"
INTEGRATION_NAME: Final[str] = "Smart Cover Automation"

# Per-cover configuration key suffixes
COVER_SFX_AZIMUTH: Final[str] = "cover_azimuth"  # Cover/window azimuth (°)
COVER_SFX_MAX_CLOSURE: Final[str] = "cover_max_closure"  # Cover maximum closure position (%)
COVER_SFX_MIN_CLOSURE: Final[str] = "cover_min_closure"  # Cover minimum closure position (%)
COVER_SFX_EVENING_CLOSURE_MAX_CLOSURE: Final[str] = (
    "cover_evening_closure_max_closure"  # Cover position (%) used specifically for evening closure.
)
COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL: Final[str] = "cover_weather_hot_external_control"  # Per-cover hot weather override.
COVER_SFX_TILT_MODE_DAY: Final[str] = "cover_tilt_mode_day"  # Per-cover tilt mode override (day)
COVER_SFX_TILT_MODE_NIGHT: Final[str] = "cover_tilt_mode_night"  # Per-cover tilt mode override (night)
COVER_SFX_TILT_EXTERNAL_VALUE_DAY: Final[str] = "cover_tilt_external_value_day"  # Per-cover externally controlled tilt value (day)
COVER_SFX_TILT_EXTERNAL_VALUE_NIGHT: Final[str] = "cover_tilt_external_value_night"  # Per-cover externally controlled tilt value (night)
COVER_SFX_WINDOW_SENSORS: Final[str] = "cover_window_sensors"  # Window sensor entity IDs

# Per-cover position history configuration
COVER_POSITION_HISTORY_SIZE: Final[int] = 3  # Number of positions to store in history
COVER_AUTOMATION_SETTLE_CYCLES: Final[int] = 2  # Coordinator cycles to tolerate recent automation settling (1 cycle + safety margin).


#
# LockMode
#
class LockMode(StrEnum):
    """Lock mode enum - single source of truth for all lock mode values."""

    UNLOCKED = "unlocked"
    HOLD_POSITION = "hold_position"
    FORCE_OPEN = "force_open"
    FORCE_CLOSE = "force_close"


#
# TiltMode
#
class EveningClosureMode(StrEnum):
    """Evening closure timing mode."""

    AFTER_SUNSET = "after_sunset"  # Close a configurable duration after sunset
    FIXED_TIME = "fixed_time"  # Close at a fixed time of day
    EXTERNAL = "external"  # Close at a time supplied via entity


#
# MorningOpeningMode
#
class MorningOpeningMode(StrEnum):
    """Morning opening timing mode."""

    RELATIVE_TO_SUNRISE = "relative_to_sunrise"  # Open relative to sunrise
    FIXED_TIME = "fixed_time"  # Open at a fixed time of day
    EXTERNAL = "external"  # Open at a time supplied via entity


#
# ReopeningMode
#
class ReopeningMode(StrEnum):
    """Automatic reopening behavior after automation-driven closing."""

    ACTIVE = "active"
    PASSIVE = "passive"
    OFF = "off"


#
# TiltMode
#
class TiltMode(StrEnum):
    """Tilt angle control mode for covers with tiltable slats."""

    OPEN = "open"  # Horizontal position — let light in (tilt = 100)
    CLOSED = "closed"  # Vertical position — block light (tilt = 0)
    MANUAL = "manual"  # Restore manually set angle after cover movement
    AUTO = "auto"  # Dynamically block direct sunlight (day only)
    EXTERNAL = "external"  # Use a Home Assistant entity to supply the tilt angle
    SET_VALUE = "set_value"  # Fixed user-specified tilt angle


# Service constants
SERVICE_SET_LOCK: Final[str] = "set_lock"  # Service name for setting lock mode
SERVICE_FIELD_LOCK_MODE: Final[str] = "lock_mode"  # Field name for lock mode parameter

# Entity keys
BINARY_SENSOR_KEY_STATUS: Final[str] = "status"  # Key for the status binary sensor entity
BINARY_SENSOR_KEY_EVENING_CLOSURE: Final[str] = "close_covers_after_sunset"  # Key for the evening closure binary sensor entity
BINARY_SENSOR_KEY_TEMP_HOT: Final[str] = "temp_hot"  # Key for the temp_hot binary sensor entity
BINARY_SENSOR_KEY_WEATHER_SUNNY: Final[str] = "weather_sunny"  # Key for the weather_sunny binary sensor entity
BINARY_SENSOR_KEY_LOCK_ACTIVE: Final[str] = "lock_active"  # Key for the lock active binary sensor entity
SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL: Final[str] = (
    "weather_sunny_external_control"  # Key for the weather sunny external control switch entity
)
SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL: Final[str] = (
    "weather_hot_external_control"  # Key for the weather hot external control switch entity
)
SWITCH_KEY_COVER_WEATHER_HOT_EXTERNAL_CONTROL: Final[str] = (
    "cover_weather_hot_external_control"  # Translation key for per-cover hot weather external control switch entities
)
SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE: Final[str] = (
    "automation_disabled_time_range"  # Key for the automation disabled time range sensor entity
)
SENSOR_KEY_EVENING_CLOSURE_TIME: Final[str] = "close_covers_after_sunset_delay"  # Key for the evening closure time sensor entity
SENSOR_KEY_EVENING_CLOSURE_MODE: Final[str] = "close_covers_after_sunset_mode"  # Key for the evening closure mode sensor entity
NUMBER_KEY_SUN_AZIMUTH_TOLERANCE: Final[str] = "sun_azimuth_tolerance"  # Key for the sun azimuth tolerance number entity
NUMBER_KEY_COVERS_MAX_CLOSURE: Final[str] = "covers_max_closure"  # Key for the covers maximum closure number entity
NUMBER_KEY_COVERS_MIN_CLOSURE: Final[str] = "covers_min_closure"  # Key for the covers minimum closure number entity
NUMBER_KEY_MANUAL_OVERRIDE_DURATION: Final[str] = "manual_override_duration"  # Key for the manual override duration number entity
NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY: Final[str] = "tilt_external_value_day"  # Key for global external tilt value number entity (day)
NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT: Final[str] = "tilt_external_value_night"  # Key for global external tilt value number entity (night)
NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_DAY: Final[str] = (
    "cover_tilt_external_value_day"  # Translation key for per-cover external tilt value number entities (day)
)
NUMBER_KEY_COVER_TILT_EXTERNAL_VALUE_NIGHT: Final[str] = (
    "cover_tilt_external_value_night"  # Translation key for per-cover external tilt value number entities (night)
)
TIME_KEY_MORNING_OPENING_EXTERNAL_TIME: Final[str] = (
    "morning_opening_external_time"  # Key for the global external morning opening time entity
)
TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME: Final[str] = (
    "evening_closure_external_time"  # Key for the global external evening closure time entity
)
SENSOR_KEY_SUN_AZIMUTH: Final[str] = "sun_azimuth"  # Key for the sun azimuth sensor entity
SENSOR_KEY_SUN_ELEVATION: Final[str] = "sun_elevation"  # Key for the sun sun_elevation sensor entity
SENSOR_KEY_TEMP_CURRENT_MAX: Final[str] = "temp_current_max"  # Key for the current maximum temperature sensor entity
SENSOR_KEY_TEMP_CURRENT_MIN: Final[str] = "temp_current_min"  # Key for the current minimum temperature sensor entity
SENSOR_KEY_LOCK_MODE: Final[str] = "lock_mode"  # Key for the lock mode sensor entity
SELECT_KEY_LOCK_MODE: Final[str] = "lock_mode"  # Key for the lock mode select entity
SELECT_KEY_AUTOMATIC_REOPENING_MODE: Final[str] = "automatic_reopening_mode"  # Key for the automatic reopening mode select entity
LEGACY_OPTION_KEY_TEMPERATURE_THRESHOLD: Final[str] = "temp_threshold"  # Legacy key for the old heat-protection max threshold option
NUMBER_KEY_DAILY_MAX_TEMPERATURE_THRESHOLD: Final[str] = (
    "daily_max_temperature_threshold"  # Key for the daily max temperature threshold number entity
)
NUMBER_KEY_DAILY_MIN_TEMPERATURE_THRESHOLD: Final[str] = (
    "daily_min_temperature_threshold"  # Key for the daily min temperature threshold number entity
)
NUMBER_KEY_SUN_ELEVATION_THRESHOLD: Final[str] = "sun_elevation_threshold"  # Key for the sun elevation threshold number entity

# Options flow translation keys
ERROR_INVALID_COVER: Final[str] = "invalid_cover"
ERROR_INVALID_WEATHER_ENTITY: Final[str] = "invalid_weather_entity"
ERROR_NO_COVERS: Final[str] = "no_covers"
ERROR_NO_WEATHER_ENTITY: Final[str] = "no_weather_entity"
STEP_3_SECTION_MAX_CLOSURE: Final[str] = "section_max_closure"
STEP_3_SECTION_MIN_CLOSURE: Final[str] = "section_min_closure"
STEP_3_SECTION_EVENING_MAX_CLOSURE: Final[str] = "section_evening_max_closure"
STEP_4_SECTION_TILT_DAY: Final[str] = "section_tilt_day"
STEP_4_SECTION_TILT_NIGHT: Final[str] = "section_tilt_night"
STEP_5_SECTION_WINDOW_SENSORS: Final[str] = "section_window_sensors"
STEP_6_SECTION_TIME_RANGE: Final[str] = "section_time_range"
STEP_6_SECTION_CLOSE_AFTER_SUNSET: Final[str] = "section_close_after_sunset"

# Home Assistant string literals
HA_OPTIONS: Final[str] = "options"
HA_SUN_ATTR_AZIMUTH: Final[str] = "azimuth"
HA_SUN_ATTR_ELEVATION: Final[str] = "elevation"
HA_SUN_ENTITY_ID: Final[str] = "sun.sun"
HA_SUN_STATE_BELOW_HORIZON: Final[str] = "below_horizon"
HA_WEATHER_COND_SUNNY: Final[str] = "sunny"
HA_WEATHER_COND_PARTCLOUDY: Final[str] = "partlycloudy"

# Weather conditions that indicate sunny conditions
WEATHER_SUNNY_CONDITIONS: Final[tuple[str, ...]] = (
    HA_WEATHER_COND_SUNNY,
    HA_WEATHER_COND_PARTCLOUDY,
)

# Home Assistant cover positions
COVER_POS_FULLY_OPEN: Final = 100
COVER_POS_FULLY_CLOSED: Final = 0

# Coordinator
UPDATE_INTERVAL: Final = timedelta(seconds=60)
SUNSET_CLOSING_WINDOW_MINUTES: Final[int] = 10  # Duration of the evening closure window

# Logbook service/translation keys
SERVICE_LOGBOOK_ENTRY: Final[str] = "logbook_entry"
TRANSL_LOGBOOK_TEMPLATE_COVER_MOVEMENT: Final[str] = "template_cover_movement"
TRANSL_LOGBOOK_VERB_OPENING: Final[str] = "verb_opening"
TRANSL_LOGBOOK_VERB_CLOSING: Final[str] = "verb_closing"
TRANSL_LOGBOOK_REASON_HEAT_PROTECTION: Final[str] = "reason_heat_protection"
TRANSL_LOGBOOK_REASON_END_HEAT_PROTECTION: Final[str] = "reason_end_heat_protection"
TRANSL_LOGBOOK_REASON_END_MANUAL_OVERRIDE: Final[str] = "reason_end_manual_override"
TRANSL_LOGBOOK_REASON_LET_LIGHT_IN: Final[str] = "reason_let_light_in"
TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET: Final[str] = "reason_close_after_sunset"
TRANSL_LOGBOOK_REASON_END_EVENING_CLOSURE: Final[str] = "reason_end_evening_closure"
TRANSL_LOGBOOK_REASON_KEEP_CLOSED_AFTER_EVENING_CLOSURE: Final[str] = "reason_keep_closed_after_evening_closure"
TRANSL_ATTR_NAME: Final[str] = "name"
TRANSL_KEY_SERVICES: Final[str] = "services"
TRANSL_KEY_FIELDS: Final[str] = "fields"

# hass.data keys
DATA_COORDINATORS: Final[str] = "coordinators"

# Persistent runtime-state storage
STORAGE_VERSION: Final[int] = 1
STORAGE_KEY_AUTOMATION_STATE: Final[str] = "automation_state"
STORAGE_KEY_AUTOMATION_CLOSED_MARKERS: Final[str] = "automation_closed_markers"
STORAGE_SAVE_DELAY_SECONDS: Final[int] = 1

# Initialize the module-level logger
_init_logger()
