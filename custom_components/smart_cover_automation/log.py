"""Unified logger for Smart Cover Automation.

This module provides a Logger-compatible wrapper.

When an entry_id is provided, all log messages are prefixed with a short
identifier (first N characters of the entry_id) to distinguish between
multiple integration instances in the logs.

Usage:
    # Without instance ID (for module-level/early logging):
    from .log import Log
    logger = Log()
    logger.info("Starting setup")  # Output: Starting setup

    # With instance ID (for instance-specific logging):
    logger = Log(entry_id="1a2b3c4d-5e6f-7890-abcd-ef1234567890")
    logger.info("Cover moved")  # Output: [1a2b3] Cover moved
"""

from __future__ import annotations

import logging
from typing import Any, Final

# Length of the short instance ID prefix used in log messages
INSTANCE_ID_LENGTH: Final[int] = 5

# Default logger for the package.
# __package__ resolves to "custom_components.smart_cover_automation.log"
# We strip the last component (.log) to get the package logger name:
# "custom_components.smart_cover_automation"
#
# This creates a logger that:
# - Inherits log level settings from parent loggers in the hierarchy
# - Can be configured in Home Assistant's configuration.yaml:
#     logger:
#       logs:
#         custom_components.smart_cover_automation: debug
_DEFAULT_LOGGER: Final = logging.getLogger(__package__.rsplit(".", 1)[0] if __package__ else __name__)


#
# Log
#
class Log:
    """Logger wrapper that optionally prefixes messages with a short instance ID.

    This class implements the commonly-used methods of the standard logging.Logger
    interface, allowing it to be used as a drop-in replacement in most contexts.
    """

    #
    # __init__
    #
    def __init__(self, entry_id: str | None = None, base_logger: logging.Logger | None = None) -> None:
        """Initialize the logger.

        Args:
            entry_id: Optional config entry ID (typically a UUID). When provided,
                      the first INSTANCE_ID_LENGTH characters are used as a prefix.
            base_logger: Optional base logger to use. Defaults to the package logger.
        """

        self._logger = base_logger or _DEFAULT_LOGGER
        self._prefix = f"[{entry_id[:INSTANCE_ID_LENGTH]}] " if entry_id else ""

    @property
    def prefix(self) -> str:
        """Return the instance prefix string (empty if no entry_id was provided)."""

        return self._prefix

    @property
    def underlying_logger(self) -> logging.Logger:
        """Return the underlying logging.Logger instance.

        This is useful when passing the logger to APIs that require
        a standard logging.Logger (e.g., Home Assistant's DataUpdateCoordinator).
        """

        return self._logger

    #
    # _format
    #
    def _format(self, msg: object) -> str:
        """Format the message with the instance prefix.

        Args:
            msg: The log message

        Returns:
            Prefixed message string (or unchanged if no prefix)
        """

        return f"{self._prefix}{msg}" if self._prefix else str(msg)

    #
    # debug
    #
    def debug(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log a debug message with optional instance prefix."""

        self._logger.debug(self._format(msg), *args, **kwargs)

    #
    # info
    #
    def info(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log an info message with optional instance prefix."""

        self._logger.info(self._format(msg), *args, **kwargs)

    #
    # warning
    #
    def warning(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log a warning message with optional instance prefix."""

        self._logger.warning(self._format(msg), *args, **kwargs)

    #
    # error
    #
    def error(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log an error message with optional instance prefix."""

        self._logger.error(self._format(msg), *args, **kwargs)

    #
    # exception
    #
    def exception(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log an exception message with optional instance prefix.

        This method should only be called from an exception handler.
        """

        self._logger.exception(self._format(msg), *args, **kwargs)

    #
    # setLevel
    #
    def setLevel(self, level: int | str) -> None:
        """Set the logging level on the underlying logger.

        Args:
            level: The logging level (e.g., logging.DEBUG, logging.INFO, "DEBUG")
        """

        self._logger.setLevel(level)

    #
    # isEnabledFor
    #
    def isEnabledFor(self, level: int) -> bool:
        """Check if the logger is enabled for the given level.

        Args:
            level: The logging level to check (e.g., logging.DEBUG)

        Returns:
            True if the logger would process messages at this level
        """

        return self._logger.isEnabledFor(level)
