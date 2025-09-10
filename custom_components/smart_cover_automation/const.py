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

from logging import getLogger
from typing import Final

LOGGER: Final = getLogger(__package__)

DOMAIN: Final = "smart_cover_automation"

# Sun position thresholds
AZIMUTH_TOLERANCE: Final[int] = 90  # Window considers sun if within this angle

# Window azimuth (degrees)
COVER_AZIMUTH: Final[str] = "cover_azimuth"
