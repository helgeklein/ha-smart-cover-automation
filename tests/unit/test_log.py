"""Tests for the Log class."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from custom_components.smart_cover_automation.log import (
    INSTANCE_ID_LENGTH,
    Log,
)


class TestLog:
    """Tests for Log."""

    #
    # test_prefix_is_short_instance_id
    #
    def test_prefix_is_short_instance_id(self) -> None:
        """Test that prefix uses first N characters of entry_id."""

        entry_id = "1a2b3c4d-5e6f-7890-abcd-ef1234567890"
        log = Log(entry_id)

        expected_prefix = f"[{entry_id[:INSTANCE_ID_LENGTH]}] "
        assert log.prefix == expected_prefix
        assert log.prefix == "[1a2b3] "

    #
    # test_prefix_with_short_entry_id
    #
    def test_prefix_with_short_entry_id(self) -> None:
        """Test that prefix works with entry_id shorter than INSTANCE_ID_LENGTH."""

        entry_id = "abc"
        log = Log(entry_id)

        assert log.prefix == "[abc] "

    #
    # test_no_prefix_when_no_entry_id
    #
    def test_no_prefix_when_no_entry_id(self) -> None:
        """Test that no prefix is added when entry_id is None."""

        log = Log()

        assert log.prefix == ""

    #
    # test_no_prefix_message_unchanged
    #
    def test_no_prefix_message_unchanged(self) -> None:
        """Test that messages are unchanged when no entry_id is provided."""

        mock_logger = MagicMock(spec=logging.Logger)
        log = Log(base_logger=mock_logger)

        log.info("Test message")

        mock_logger.info.assert_called_once_with("Test message")

    #
    # test_debug_prefixes_message
    #
    def test_debug_prefixes_message(self) -> None:
        """Test that debug() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        log = Log("test123456", mock_logger)

        log.debug("Test message")

        mock_logger.debug.assert_called_once_with("[test1] Test message")

    #
    # test_info_prefixes_message
    #
    def test_info_prefixes_message(self) -> None:
        """Test that info() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        log = Log("test123456", mock_logger)

        log.info("Test message")

        mock_logger.info.assert_called_once_with("[test1] Test message")

    #
    # test_warning_prefixes_message
    #
    def test_warning_prefixes_message(self) -> None:
        """Test that warning() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        log = Log("test123456", mock_logger)

        log.warning("Test message")

        mock_logger.warning.assert_called_once_with("[test1] Test message")

    #
    # test_error_prefixes_message
    #
    def test_error_prefixes_message(self) -> None:
        """Test that error() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        log = Log("test123456", mock_logger)

        log.error("Test message")

        mock_logger.error.assert_called_once_with("[test1] Test message")

    #
    # test_exception_prefixes_message
    #
    def test_exception_prefixes_message(self) -> None:
        """Test that exception() prefixes the message."""

        mock_logger = MagicMock(spec=logging.Logger)
        log = Log("test123456", mock_logger)

        log.exception("Test message")

        mock_logger.exception.assert_called_once_with("[test1] Test message")

    #
    # test_passes_args_to_underlying_logger
    #
    def test_passes_args_to_underlying_logger(self) -> None:
        """Test that positional args are passed through."""

        mock_logger = MagicMock(spec=logging.Logger)
        log = Log("test123456", mock_logger)

        log.info("Value is %s and %d", "hello", 42)

        mock_logger.info.assert_called_once_with("[test1] Value is %s and %d", "hello", 42)

    #
    # test_passes_kwargs_to_underlying_logger
    #
    def test_passes_kwargs_to_underlying_logger(self) -> None:
        """Test that keyword args are passed through."""

        mock_logger = MagicMock(spec=logging.Logger)
        log = Log("test123456", mock_logger)

        log.info("Test message", exc_info=True, stack_info=True)

        mock_logger.info.assert_called_once_with("[test1] Test message", exc_info=True, stack_info=True)

    #
    # test_set_level_delegates_to_underlying_logger
    #
    def test_set_level_delegates_to_underlying_logger(self) -> None:
        """Test that setLevel() is delegated to the underlying logger."""

        mock_logger = MagicMock(spec=logging.Logger)
        log = Log("test123456", mock_logger)

        log.setLevel(logging.DEBUG)

        mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    #
    # test_is_enabled_for_delegates_to_underlying_logger
    #
    def test_is_enabled_for_delegates_to_underlying_logger(self) -> None:
        """Test that isEnabledFor() is delegated to the underlying logger."""

        mock_logger = MagicMock(spec=logging.Logger)
        mock_logger.isEnabledFor.return_value = True
        log = Log("test123456", mock_logger)

        result = log.isEnabledFor(logging.DEBUG)

        assert result is True
        mock_logger.isEnabledFor.assert_called_once_with(logging.DEBUG)

    #
    # test_uses_default_logger_when_none_provided
    #
    def test_uses_default_logger_when_none_provided(self) -> None:
        """Test that the default logger is used when no base_logger is provided."""

        from custom_components.smart_cover_automation.log import _DEFAULT_LOGGER

        log = Log("test123456")

        # Verify it uses the default logger by checking the internal attribute
        assert log._logger is _DEFAULT_LOGGER

    #
    # test_logger_from_const_has_no_prefix
    #
    def test_logger_from_const_has_no_prefix(self) -> None:
        """Test that LOGGER from const.py has no prefix (no entry_id)."""

        from custom_components.smart_cover_automation.const import LOGGER

        assert LOGGER.prefix == ""
