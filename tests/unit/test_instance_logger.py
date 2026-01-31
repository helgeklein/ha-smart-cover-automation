"""Tests for the InstanceLogger class."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from custom_components.smart_cover_automation.instance_logger import (
    INSTANCE_ID_LENGTH,
    InstanceLogger,
)


class TestInstanceLogger:
    """Tests for InstanceLogger."""

    #
    # test_prefix_is_short_instance_id
    #
    def test_prefix_is_short_instance_id(self) -> None:
        """Test that prefix uses first N characters of entry_id."""

        entry_id = "1a2b3c4d-5e6f-7890-abcd-ef1234567890"
        logger = InstanceLogger(entry_id)

        expected_prefix = f"[{entry_id[:INSTANCE_ID_LENGTH]}] "
        assert logger.prefix == expected_prefix
        assert logger.prefix == "[1a2b3c] "

    #
    # test_prefix_with_short_entry_id
    #
    def test_prefix_with_short_entry_id(self) -> None:
        """Test that prefix works with entry_id shorter than INSTANCE_ID_LENGTH."""

        entry_id = "abc"
        logger = InstanceLogger(entry_id)

        assert logger.prefix == "[abc] "

    #
    # test_debug_prefixes_message
    #
    def test_debug_prefixes_message(self) -> None:
        """Test that debug() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        logger = InstanceLogger("test123456", mock_logger)

        logger.debug("Test message")

        mock_logger.debug.assert_called_once_with("[test12] Test message")

    #
    # test_info_prefixes_message
    #
    def test_info_prefixes_message(self) -> None:
        """Test that info() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        logger = InstanceLogger("test123456", mock_logger)

        logger.info("Test message")

        mock_logger.info.assert_called_once_with("[test12] Test message")

    #
    # test_warning_prefixes_message
    #
    def test_warning_prefixes_message(self) -> None:
        """Test that warning() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        logger = InstanceLogger("test123456", mock_logger)

        logger.warning("Test message")

        mock_logger.warning.assert_called_once_with("[test12] Test message")

    #
    # test_error_prefixes_message
    #
    def test_error_prefixes_message(self) -> None:
        """Test that error() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        logger = InstanceLogger("test123456", mock_logger)

        logger.error("Test message")

        mock_logger.error.assert_called_once_with("[test12] Test message")

    #
    # test_exception_prefixes_message
    #
    def test_exception_prefixes_message(self) -> None:
        """Test that exception() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        logger = InstanceLogger("test123456", mock_logger)

        logger.exception("Test message")

        mock_logger.exception.assert_called_once_with("[test12] Test message")

    #
    # test_passes_args_to_underlying_logger
    #
    def test_passes_args_to_underlying_logger(self) -> None:
        """Test that positional args are passed through."""

        mock_logger = MagicMock(spec=logging.Logger)
        logger = InstanceLogger("test123456", mock_logger)

        logger.info("Value is %s and %d", "hello", 42)

        mock_logger.info.assert_called_once_with("[test12] Value is %s and %d", "hello", 42)

    #
    # test_passes_kwargs_to_underlying_logger
    #
    def test_passes_kwargs_to_underlying_logger(self) -> None:
        """Test that keyword args are passed through."""

        mock_logger = MagicMock(spec=logging.Logger)
        logger = InstanceLogger("test123456", mock_logger)

        logger.info("Test message", exc_info=True, stack_info=True)

        mock_logger.info.assert_called_once_with("[test12] Test message", exc_info=True, stack_info=True)

    #
    # test_set_level_delegates_to_underlying_logger
    #
    def test_set_level_delegates_to_underlying_logger(self) -> None:
        """Test that setLevel() is delegated to the underlying logger."""

        mock_logger = MagicMock(spec=logging.Logger)
        logger = InstanceLogger("test123456", mock_logger)

        logger.setLevel(logging.DEBUG)

        mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    #
    # test_is_enabled_for_delegates_to_underlying_logger
    #
    def test_is_enabled_for_delegates_to_underlying_logger(self) -> None:
        """Test that isEnabledFor() is delegated to the underlying logger."""

        mock_logger = MagicMock(spec=logging.Logger)
        mock_logger.isEnabledFor.return_value = True
        logger = InstanceLogger("test123456", mock_logger)

        result = logger.isEnabledFor(logging.DEBUG)

        assert result is True
        mock_logger.isEnabledFor.assert_called_once_with(logging.DEBUG)

    #
    # test_uses_default_logger_when_none_provided
    #
    def test_uses_default_logger_when_none_provided(self) -> None:
        """Test that the default LOGGER is used when no base_logger is provided."""

        from custom_components.smart_cover_automation.instance_logger import _DEFAULT_LOGGER

        logger = InstanceLogger("test123456")

        # Verify it uses the default logger by checking the internal attribute
        assert logger._logger is _DEFAULT_LOGGER
