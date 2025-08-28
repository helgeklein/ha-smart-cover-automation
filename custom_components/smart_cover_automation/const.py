"""Constants for smart_cover_automation."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "smart_cover_automation"

# Configuration
CONF_AUTOMATION_TYPE = "automation_type"
CONF_MAX_TEMP = "max_temperature"
CONF_MIN_TEMP = "min_temperature"
CONF_COVERS = "covers"
CONF_SUN_ELEVATION_THRESHOLD = "sun_elevation_threshold"
CONF_COVER_DIRECTION = "cover_direction"

# Defaults
DEFAULT_MAX_TEMP = 24
DEFAULT_MIN_TEMP = 21
DEFAULT_SUN_ELEVATION_THRESHOLD = 20  # degrees

# Cover directions (which way the window faces)
DIRECTION_NORTH = "north"
DIRECTION_NORTHEAST = "northeast"
DIRECTION_EAST = "east"
DIRECTION_SOUTHEAST = "southeast"
DIRECTION_SOUTH = "south"
DIRECTION_SOUTHWEST = "southwest"
DIRECTION_WEST = "west"
DIRECTION_NORTHWEST = "northwest"

COVER_DIRECTIONS = [
    DIRECTION_NORTH,
    DIRECTION_NORTHEAST,
    DIRECTION_EAST,
    DIRECTION_SOUTHEAST,
    DIRECTION_SOUTH,
    DIRECTION_SOUTHWEST,
    DIRECTION_WEST,
    DIRECTION_NORTHWEST,
]

# Automation types
AUTOMATION_TYPE_TEMPERATURE = "temperature"
AUTOMATION_TYPE_SUN = "sun"
AUTOMATION_TYPES = [
    AUTOMATION_TYPE_TEMPERATURE,
    AUTOMATION_TYPE_SUN,
]

# Sun position thresholds
AZIMUTH_TOLERANCE = 45  # degrees - window considers sun if within this angle
MAX_CLOSURE = 90  # Maximum closure percentage when sun is directly at window
