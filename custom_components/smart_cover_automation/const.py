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


DOMAIN: Final[str] = "smart_cover_automation"
INTEGRATION_NAME: Final[str] = "Smart Cover Automation"

# Per-cover configuration key suffixes
COVER_SFX_AZIMUTH: Final[str] = "cover_azimuth"  # Cover/window azimuth (°)

# Per-cover position history configuration
COVER_POSITION_HISTORY_SIZE: Final[int] = 3  # Number of positions to store in history

# Cover translation keys
COVER_AZIMUTH: Final[str] = "cover_azimuth"  # Translation key for cover/window azimuth (°)

# Entity keys
BINARY_SENSOR_KEY_STATUS: Final[str] = "status"  # Key for the status binary sensor entity
BINARY_SENSOR_KEY_TEMP_HOT: Final[str] = "temp_hot"  # Key for the temp_hot binary sensor entity
BINARY_SENSOR_KEY_WEATHER_SUNNY: Final[str] = "weather_sunny"  # Key for the weather_sunny binary sensor entity
SENSOR_KEY_LAST_MOVEMENT_TIMESTAMP: Final[str] = "last_movement_timestamp"  # Key for the last movement timestamp sensor entity
SENSOR_KEY_SUN_AZIMUTH: Final[str] = "sun_azimuth"  # Key for the sun azimuth sensor entity
SENSOR_KEY_SUN_ELEVATION: Final[str] = "sun_elevation"  # Key for the sun sun_elevation sensor entity

# Cover attribute keys (exposed on each cover entity)
COVER_ATTR_COVER_AZIMUTH: Final[str] = "cover_azimuth"  # Cover/window azimuth (°)
COVER_ATTR_MESSAGE: Final[str] = "cover_message"  # Info or error message for this cover
COVER_ATTR_POS_CURRENT: Final[str] = "cover_pos_current"  # Current cover position
COVER_ATTR_POS_HISTORY: Final[str] = "cover_pos_history"  # Position history
COVER_ATTR_POS_TARGET_DESIRED: Final[str] = "cover_pos_target_desired"  # Desired cover target cover position
COVER_ATTR_POS_TARGET_FINAL: Final[str] = "cover_pos_target_final"  # Final cover target position after adjustments
COVER_ATTR_STATE: Final[str] = "cover_state"  # Current state of the cover (e.g., 'open', 'closed', 'opening', 'closing', 'stopped')
COVER_ATTR_SUN_AZIMUTH_DIFF: Final[str] = "cover_sun_azimuth_diff"  # Difference between sun azimuth and cover azimuth (°)
COVER_ATTR_SUN_HITTING: Final[str] = "cover_sun_hitting"  # Whether the sun is hitting the window
COVER_ATTR_SUPPORTED_FEATURES: Final[str] = "cover_supported_features"  # Supported cover features bitmask

# Options flow translation keys
ERROR_INVALID_COVER: Final[str] = "invalid_cover"
ERROR_INVALID_WEATHER_ENTITY: Final[str] = "invalid_weather_entity"
ERROR_NO_COVERS: Final[str] = "no_covers"
ERROR_NO_WEATHER_ENTITY: Final[str] = "no_weather_entity"

# Home Assistant string literals
HA_OPTIONS: Final[str] = "options"
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
