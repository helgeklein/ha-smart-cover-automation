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

from datetime import timedelta
from enum import Enum, StrEnum
from logging import getLogger
from typing import Final

LOGGER: Final = getLogger(__package__)


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
COVER_SFX_WINDOW_SENSORS: Final[str] = "cover_window_sensors"  # Window sensor entity IDs

# Per-cover position history configuration
COVER_POSITION_HISTORY_SIZE: Final[int] = 3  # Number of positions to store in history


#
# LockMode
#
class LockMode(StrEnum):
    """Lock mode enum - single source of truth for all lock mode values."""

    UNLOCKED = "unlocked"
    HOLD_POSITION = "hold_position"
    FORCE_OPEN = "force_open"
    FORCE_CLOSE = "force_close"


# Service constants
SERVICE_SET_LOCK: Final[str] = "set_lock"  # Service name for setting lock mode
SERVICE_FIELD_LOCK_MODE: Final[str] = "lock_mode"  # Field name for lock mode parameter

# Entity keys
BINARY_SENSOR_KEY_STATUS: Final[str] = "status"  # Key for the status binary sensor entity
BINARY_SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET: Final[str] = (
    "close_covers_after_sunset"  # Key for the close covers after sunset binary sensor entity
)
BINARY_SENSOR_KEY_NIGHTTIME_BLOCK_OPENING: Final[str] = (
    "nighttime_block_opening"  # Key for the nighttime block opening binary sensor entity
)
BINARY_SENSOR_KEY_TEMP_HOT: Final[str] = "temp_hot"  # Key for the temp_hot binary sensor entity
BINARY_SENSOR_KEY_WEATHER_SUNNY: Final[str] = "weather_sunny"  # Key for the weather_sunny binary sensor entity
BINARY_SENSOR_KEY_LOCK_ACTIVE: Final[str] = "lock_active"  # Key for the lock active binary sensor entity
SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE: Final[str] = (
    "automation_disabled_time_range"  # Key for the automation disabled time range sensor entity
)
SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET_DELAY: Final[str] = (
    "close_covers_after_sunset_delay"  # Key for the close covers after sunset delay sensor entity
)
SENSOR_KEY_SUN_AZIMUTH: Final[str] = "sun_azimuth"  # Key for the sun azimuth sensor entity
SENSOR_KEY_SUN_ELEVATION: Final[str] = "sun_elevation"  # Key for the sun sun_elevation sensor entity
SENSOR_KEY_TEMP_CURRENT_MAX: Final[str] = "temp_current_max"  # Key for the current maximum temperature sensor entity
SENSOR_KEY_LOCK_MODE: Final[str] = "lock_mode"  # Key for the lock mode sensor entity
SELECT_KEY_LOCK_MODE: Final[str] = "lock_mode"  # Key for the lock mode select entity
NUMBER_KEY_TEMP_THRESHOLD: Final[str] = "temp_threshold"  # Key for the temperature threshold number entity
NUMBER_KEY_SUN_ELEVATION_THRESHOLD: Final[str] = "sun_elevation_threshold"  # Key for the sun elevation threshold number entity

# Options flow translation keys
ERROR_INVALID_COVER: Final[str] = "invalid_cover"
ERROR_INVALID_WEATHER_ENTITY: Final[str] = "invalid_weather_entity"
ERROR_NO_COVERS: Final[str] = "no_covers"
ERROR_NO_WEATHER_ENTITY: Final[str] = "no_weather_entity"
STEP_4_SECTION_MAX_CLOSURE: Final[str] = "section_max_closure"
STEP_4_SECTION_MIN_CLOSURE: Final[str] = "section_min_closure"
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

# Logbook service/translation keys
SERVICE_LOGBOOK_ENTRY: Final[str] = "logbook_entry"
TRANSL_LOGBOOK_TEMPLATE_COVER_MOVEMENT: Final[str] = "template_cover_movement"
TRANSL_LOGBOOK_VERB_OPENING: Final[str] = "verb_opening"
TRANSL_LOGBOOK_VERB_CLOSING: Final[str] = "verb_closing"
TRANSL_LOGBOOK_REASON_HEAT_PROTECTION: Final[str] = "reason_heat_protection"
TRANSL_LOGBOOK_REASON_LET_LIGHT_IN: Final[str] = "reason_let_light_in"
TRANSL_LOGBOOK_REASON_CLOSE_AFTER_SUNSET: Final[str] = "reason_close_after_sunset"
TRANSL_ATTR_NAME: Final[str] = "name"
TRANSL_KEY_SERVICES: Final[str] = "services"
TRANSL_KEY_FIELDS: Final[str] = "fields"

# hass.data keys
DATA_COORDINATORS: Final[str] = "coordinators"
