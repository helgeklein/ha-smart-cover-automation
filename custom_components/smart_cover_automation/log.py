"""Unified logger for Smart Cover Automation.

This module provides a Logger-compatible wrapper using child loggers.

When an entry_id is provided, a child logger is created using the last N
characters of the entry_id. This allows per-instance log level control
(verbose mode) without affecting other instances.

Usage:
    # Without instance ID (for module-level/early logging):
    from .log import Log
    logger = Log()
    logger.info("Starting setup")
    # Output: [custom_components.smart_cover_automation] Starting setup

    # With instance ID (for instance-specific logging):
    logger = Log(entry_id="1a2b3c4d-5e6f-7890-abcd-ef1234567890")
    logger.info("Cover moved")
    # Output: [custom_components.smart_cover_automation.67890] Cover moved

    # Enable verbose mode for ONE instance only:
    logger.setLevel(logging.DEBUG)
    # Only this instance outputs DEBUG messages
"""

from __future__ import annotations

import logging
from typing import Any, Final

# Length of the short instance ID suffix used in child logger names
INSTANCE_ID_LENGTH: Final[int] = 5

# Base logger name for the integration.
# __package__ is "custom_components.smart_cover_automation" when imported as a package.
_BASE_LOGGER_NAME: Final[str] = __package__ or __name__.rsplit(".", 1)[0]


#
# Log
#
class Log:
    """Logger wrapper using child loggers for per-instance log level control.

    When an entry_id is provided, creates a child logger with the last N
    characters of the entry_id appended to the base logger name. This allows
    setLevel() to affect only this instance.

    This class implements the commonly-used methods of the standard logging.Logger
    interface, allowing it to be used as a drop-in replacement in most contexts.
    """

    #
    # __init__
    #
    def __init__(self, entry_id: str | None = None) -> None:
        """Initialize the logger.

        Args:
            entry_id: Optional config entry ID (typically a UUID). When provided,
                      creates a child logger using the last INSTANCE_ID_LENGTH
                      characters, enabling per-instance log level control.
        """

        if entry_id:
            short_id = entry_id[-INSTANCE_ID_LENGTH:]
            self._logger = logging.getLogger(f"{_BASE_LOGGER_NAME}.{short_id}")
        else:
            self._logger = logging.getLogger(_BASE_LOGGER_NAME)

    @property
    def underlying_logger(self) -> logging.Logger:
        """Return the underlying logging.Logger instance.

        This is useful when passing the logger to APIs that require
        a standard logging.Logger (e.g., Home Assistant's DataUpdateCoordinator).
        """

        return self._logger

    #
    # debug
    #
    def debug(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log a debug message."""

        self._logger.debug(msg, *args, **kwargs)

    #
    # info
    #
    def info(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log an info message."""

        self._logger.info(msg, *args, **kwargs)

    #
    # warning
    #
    def warning(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log a warning message."""

        self._logger.warning(msg, *args, **kwargs)

    #
    # error
    #
    def error(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log an error message."""

        self._logger.error(msg, *args, **kwargs)

    #
    # exception
    #
    def exception(self, msg: object, *args: object, **kwargs: Any) -> None:
        """Log an exception message.

        This method should only be called from an exception handler.
        """

        self._logger.exception(msg, *args, **kwargs)

    #
    # setLevel
    #
    def setLevel(self, level: int | str) -> None:
        """Set the logging level for this instance.

        When entry_id was provided, this only affects this instance's child
        logger. Other instances remain at their default level.

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
