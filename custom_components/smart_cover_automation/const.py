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
from enum import Enum
from logging import getLogger
from typing import Final

LOGGER: Final = getLogger(__package__)


class LogSeverity(Enum):
    """Log severity levels for structured logging."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


DOMAIN: Final = "smart_cover_automation"
INTEGRATION_NAME: Final = "Smart Cover Automation"

# Per-cover configuration key suffixes
COVER_SFX_AZIMUTH: Final[str] = "cover_azimuth"  # Cover/window azimuth (°)

# Per-cover position history configuration
COVER_POSITION_HISTORY_SIZE: Final[int] = 3  # Number of positions to store in history

# Cover translation keys
COVER_AZIMUTH: Final[str] = "cover_azimuth"  # Translation key for cover/window azimuth (°)

# Sensor entity keys
SENSOR_KEY_AUTOMATION_STATUS: Final[str] = "automation_status"  # Key for the automation status sensor entity

# Sensor attribute keys (exposed on the automation status sensor)
SENSOR_ATTR_AUTOMATION_ENABLED: Final[str] = "automation_enabled"  # Config value
SENSOR_ATTR_COVERS_MAX_CLOSURE_POS: Final[str] = "covers_max_closure_pos"  # Config value
SENSOR_ATTR_COVERS_MIN_CLOSURE_POS: Final[str] = "covers_min_closure_pos"  # Config value
SENSOR_ATTR_COVERS_MIN_POSITION_DELTA: Final[str] = "covers_min_position_delta"  # Config value
SENSOR_ATTR_COVERS_NUM_MOVED: Final[str] = "covers_num_moved"  # Current value
SENSOR_ATTR_COVERS_NUM_TOTAL: Final[str] = "covers_num_total"  # Current value
SENSOR_ATTR_MESSAGE: Final[str] = "message"  # Info or error message for the integration
SENSOR_ATTR_MANUAL_OVERRIDE_DURATION: Final[str] = "manual_override_duration"  # Config value
SENSOR_ATTR_SIMULATION_ENABLED: Final[str] = "simulation_enabled"  # Config value
SENSOR_ATTR_TEMP_CURRENT_MAX: Final[str] = "temp_current_max"  # Current value
SENSOR_ATTR_TEMP_HOT: Final[str] = "temp_hot"  # Current value
SENSOR_ATTR_TEMP_THRESHOLD: Final[str] = "temp_threshold"  # Config value
SENSOR_ATTR_SUN_AZIMUTH: Final[str] = "sun_azimuth"  # Current value
SENSOR_ATTR_SUN_AZIMUTH_TOLERANCE: Final[str] = "sun_azimuth_tolerance"  # Config value
SENSOR_ATTR_SUN_ELEVATION: Final[str] = "sun_elevation"  # Current value
SENSOR_ATTR_SUN_ELEVATION_THRESH: Final[str] = "sun_elevation_threshold"  # Config value
SENSOR_ATTR_WEATHER_ENTITY_ID: Final[str] = "weather_entity_id"  # Config value
SENSOR_ATTR_WEATHER_SUNNY: Final[str] = "weather_sunny"  # Current value

# Cover attribute keys (exposed on each cover entity)
COVER_ATTR_COVER_AZIMUTH: Final[str] = "cover_azimuth"  # Cover/window azimuth (°)
COVER_ATTR_MESSAGE: Final[str] = "cover_message"  # Info or error message for this cover
COVER_ATTR_POS_CURRENT: Final[str] = "cover_pos_current"  # Current cover position
COVER_ATTR_POS_HISTORY_ALL: Final[str] = "cover_pos_history_all"  # All position history (last 5 positions)
COVER_ATTR_POS_TARGET_DESIRED: Final[str] = "cover_pos_target_desired"  # Desired cover target cover position
COVER_ATTR_POS_TARGET_FINAL: Final[str] = "cover_pos_target_final"  # Final cover target position after adjustments
COVER_ATTR_STATE: Final[str] = "cover_state"  # Current state of the cover (e.g., 'open', 'closed', 'opening', 'closing', 'stopped')
COVER_ATTR_SUN_AZIMUTH_DIFF: Final[str] = "cover_sun_azimuth_diff"  # Difference between sun azimuth and cover azimuth (°)
COVER_ATTR_SUN_HITTING: Final[str] = "cover_sun_hitting"  # Whether the sun is hitting the window
COVER_ATTR_SUPPORTED_FEATURES: Final[str] = "cover_supported_features"  # Supported cover features bitmask

# Translation keys used by config flows and tests
ERROR_INVALID_CONFIG: Final[str] = "invalid_config"
ERROR_INVALID_COVER: Final[str] = "invalid_cover"
ERROR_INVALID_WEATHER_ENTITY: Final[str] = "invalid_weather_entity"

# Abort reasons
ABORT_SINGLE_INSTANCE_ALLOWED: Final[str] = "single_instance_allowed"

# Home Assistant string literals
HA_OPTIONS: Final = "options"
HA_SUN_ATTR_AZIMUTH: Final[str] = "azimuth"
HA_SUN_ATTR_ELEVATION: Final[str] = "elevation"
HA_SUN_ENTITY_ID: Final[str] = "sun.sun"
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
