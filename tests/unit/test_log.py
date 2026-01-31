"""Tests for the Log class."""

from __future__ import annotations

import logging

from custom_components.smart_cover_automation.log import (
    _BASE_LOGGER_NAME,
    INSTANCE_ID_LENGTH,
    Log,
)


class TestLog:
    """Tests for Log."""

    #
    # test_uses_last_n_chars_of_entry_id
    #
    def test_uses_last_n_chars_of_entry_id(self) -> None:
        """Test that child logger uses last N characters of entry_id."""

        entry_id = "1a2b3c4d-5e6f-7890-abcd-ef1234567890"
        log = Log(entry_id)

        expected_suffix = entry_id[-INSTANCE_ID_LENGTH:]
        expected_name = f"{_BASE_LOGGER_NAME}.{expected_suffix}"
        assert log.underlying_logger.name == expected_name
        assert log.underlying_logger.name == "custom_components.smart_cover_automation.67890"

    #
    # test_short_entry_id
    #
    def test_short_entry_id(self) -> None:
        """Test that short entry_id works correctly."""

        entry_id = "abc"
        log = Log(entry_id)

        # Last 5 chars of "abc" is just "abc"
        assert log.underlying_logger.name == f"{_BASE_LOGGER_NAME}.abc"

    #
    # test_no_entry_id_uses_base_logger
    #
    def test_no_entry_id_uses_base_logger(self) -> None:
        """Test that no entry_id uses the base logger."""

        log = Log()

        assert log.underlying_logger.name == _BASE_LOGGER_NAME
        assert log.underlying_logger.name == "custom_components.smart_cover_automation"

    #
    # test_debug_logs_message
    #
    def test_debug_logs_message(self, caplog: object) -> None:
        """Test that debug() logs the message."""

        log = Log("test123456")
        logger_name = log.underlying_logger.name

        with caplog.at_level(logging.DEBUG, logger=logger_name):  # type: ignore[attr-defined]
            log.debug("Test message")

        assert "Test message" in caplog.text  # type: ignore[attr-defined]

    #
    # test_info_logs_message
    #
    def test_info_logs_message(self, caplog: object) -> None:
        """Test that info() logs the message."""

        log = Log("test123456")
        logger_name = log.underlying_logger.name

        with caplog.at_level(logging.INFO, logger=logger_name):  # type: ignore[attr-defined]
            log.info("Test message")

        assert "Test message" in caplog.text  # type: ignore[attr-defined]

    #
    # test_warning_logs_message
    #
    def test_warning_logs_message(self, caplog: object) -> None:
        """Test that warning() logs the message."""

        log = Log("test123456")
        logger_name = log.underlying_logger.name

        with caplog.at_level(logging.WARNING, logger=logger_name):  # type: ignore[attr-defined]
            log.warning("Test message")

        assert "Test message" in caplog.text  # type: ignore[attr-defined]

    #
    # test_error_logs_message
    #
    def test_error_logs_message(self, caplog: object) -> None:
        """Test that error() logs the message."""

        log = Log("test123456")
        logger_name = log.underlying_logger.name

        with caplog.at_level(logging.ERROR, logger=logger_name):  # type: ignore[attr-defined]
            log.error("Test message")

        assert "Test message" in caplog.text  # type: ignore[attr-defined]

    #
    # test_exception_logs_message
    #
    def test_exception_logs_message(self, caplog: object) -> None:
        """Test that exception() logs the message."""

        log = Log("test123456")
        logger_name = log.underlying_logger.name

        with caplog.at_level(logging.ERROR, logger=logger_name):  # type: ignore[attr-defined]
            try:
                raise ValueError("test error")
            except ValueError:
                log.exception("Test message")

        assert "Test message" in caplog.text  # type: ignore[attr-defined]

    #
    # test_passes_args_to_underlying_logger
    #
    def test_passes_args_to_underlying_logger(self, caplog: object) -> None:
        """Test that positional args are passed through for formatting."""

        log = Log("test123456")
        logger_name = log.underlying_logger.name

        with caplog.at_level(logging.INFO, logger=logger_name):  # type: ignore[attr-defined]
            log.info("Value is %s and %d", "hello", 42)

        assert "Value is hello and 42" in caplog.text  # type: ignore[attr-defined]

    #
    # test_passes_kwargs_to_underlying_logger
    #
    def test_passes_kwargs_to_underlying_logger(self, caplog: object) -> None:
        """Test that keyword args (like exc_info) are passed through."""

        log = Log("test123456")
        logger_name = log.underlying_logger.name

        with caplog.at_level(logging.INFO, logger=logger_name):  # type: ignore[attr-defined]
            log.info("Test message", exc_info=False)

        assert "Test message" in caplog.text  # type: ignore[attr-defined]

    #
    # test_set_level_affects_only_own_instance
    #
    def test_set_level_affects_only_own_instance(self) -> None:
        """Test that setLevel only affects this instance's child logger."""

        # Two instances with different entry_ids
        log1 = Log("instance_one")
        log2 = Log("instance_two")

        # Enable DEBUG only on log1
        log1.setLevel(logging.DEBUG)

        # log2 should NOT have DEBUG enabled (inherits from parent)
        # We verify by checking the logger's level
        assert log1.underlying_logger.level == logging.DEBUG
        assert log2.underlying_logger.level == logging.NOTSET  # Inherits from parent

    #
    # test_is_enabled_for_delegates_to_underlying_logger
    #
    def test_is_enabled_for_delegates_to_underlying_logger(self) -> None:
        """Test that isEnabledFor() is delegated to the underlying logger."""

        log = Log("test123456")

        # Set level to INFO, so DEBUG should not be enabled
        log.setLevel(logging.INFO)

        assert log.isEnabledFor(logging.INFO) is True
        assert log.isEnabledFor(logging.DEBUG) is False

    #
    # test_verbose_mode_per_instance
    #
    def test_verbose_mode_per_instance(self) -> None:
        """Test that enabling verbose on one instance doesn't affect others."""

        log1 = Log("aaaaa11111")
        log2 = Log("bbbbb22222")

        # Before enabling verbose
        assert log1.underlying_logger.level == logging.NOTSET
        assert log2.underlying_logger.level == logging.NOTSET

        # Enable verbose (DEBUG) only on log1
        log1.setLevel(logging.DEBUG)

        # log1 has DEBUG, log2 still has NOTSET
        assert log1.underlying_logger.level == logging.DEBUG
        assert log2.underlying_logger.level == logging.NOTSET

        # Verify logger names are different
        assert log1.underlying_logger.name == f"{_BASE_LOGGER_NAME}.11111"
        assert log2.underlying_logger.name == f"{_BASE_LOGGER_NAME}.22222"

    #
    # test_logger_from_const_uses_base_logger
    #
    def test_logger_from_const_uses_base_logger(self) -> None:
        """Test that LOGGER from const.py uses the base logger name."""

        from custom_components.smart_cover_automation.const import LOGGER

        assert LOGGER.underlying_logger.name == _BASE_LOGGER_NAME

    #
    # test_child_logger_inherits_from_parent
    #
    def test_child_logger_inherits_from_parent(self) -> None:
        """Test that child loggers inherit level from parent when not set."""

        parent_logger = logging.getLogger(_BASE_LOGGER_NAME)
        original_level = parent_logger.level

        try:
            # Set parent to WARNING
            parent_logger.setLevel(logging.WARNING)

            # Create child logger (doesn't set its own level)
            log = Log("test12345")

            # Child should inherit effective level from parent
            assert log.underlying_logger.getEffectiveLevel() == logging.WARNING
        finally:
            # Restore original level
            parent_logger.setLevel(original_level)
