"""Instance-specific logger for Smart Cover Automation.

This module provides a logger wrapper that automatically prefixes log messages
with a short instance ID, allowing easy identification of which integration
instance generated each log entry when multiple instances are configured.
"""

from __future__ import annotations

from logging import Logger, getLogger
from typing import Any, Final

# Length of the short instance ID prefix used in log messages
INSTANCE_ID_LENGTH: Final[int] = 5

# Default logger for the package
_DEFAULT_LOGGER: Final = getLogger(__package__.rsplit(".", 1)[0] if __package__ else __name__)


#
# InstanceLogger
#
class InstanceLogger:
    """Logger wrapper that prefixes all messages with a short instance ID.

    This allows distinguishing log messages from different integration instances
    when multiple Smart Cover Automation configurations are active.

    Usage:
        logger = InstanceLogger(entry_id="1a2b3c4d-5e6f-7890-abcd-ef1234567890")
        logger.info("Cover moved to position 50")
        # Output: [1a2b3c] Cover moved to position 50
    """

    #
    # __init__
    #
    def __init__(self, entry_id: str, base_logger: Logger | None = None) -> None:
        """Initialize the instance logger.

        Args:
            entry_id: The config entry ID (typically a UUID).
            base_logger: Optional base logger to use. Defaults to the module logger.
        """

        self._logger = base_logger or _DEFAULT_LOGGER
        self._prefix = f"[{entry_id[:INSTANCE_ID_LENGTH]}] "

    @property
    def prefix(self) -> str:
        """Return the instance prefix string."""

        return self._prefix

    #
    # _format
    #
    def _format(self, msg: object) -> str:
        """Format the message with the instance prefix.

        Args:
            msg: The log message

        Returns:
            Prefixed message string
        """

        return f"{self._prefix}{msg}"

    #
    # debug
    #
    def debug(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log a debug message with instance prefix."""

        self._logger.debug(self._format(msg), *args, **kwargs)

    #
    # info
    #
    def info(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log an info message with instance prefix."""

        self._logger.info(self._format(msg), *args, **kwargs)

    #
    # warning
    #
    def warning(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log a warning message with instance prefix."""

        self._logger.warning(self._format(msg), *args, **kwargs)

    #
    # error
    #
    def error(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log an error message with instance prefix."""

        self._logger.error(self._format(msg), *args, **kwargs)

    #
    # exception
    #
    def exception(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log an exception message with instance prefix."""

        self._logger.exception(self._format(msg), *args, **kwargs)

    #
    # setLevel
    #
    def setLevel(self, level: int | str) -> None:
        """Set the logging level on the underlying logger."""

        self._logger.setLevel(level)

    #
    # isEnabledFor
    #
    def isEnabledFor(self, level: int) -> bool:
        """Check if the logger is enabled for the given level."""

        return self._logger.isEnabledFor(level)
