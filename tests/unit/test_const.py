"""Tests for const.py module.

This module tests the `_init_logger()` function, particularly the ImportError
fallback path that uses importlib to load log.py directly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestInitLogger:
    """Tests for _init_logger function."""

    #
    # test_init_logger_fallback_on_import_error
    #
    def test_init_logger_fallback_on_import_error(self) -> None:
        """Test that _init_logger falls back to importlib when relative import fails.

        This tests the except ImportError branch (lines 49-62) in const.py.
        """

        from custom_components.smart_cover_automation import const

        const_dir = Path(const.__file__).parent
        expected_log_path = const_dir / "log.py"

        # Mock the importlib.util functions
        mock_spec = MagicMock()
        mock_spec.loader = MagicMock()
        mock_log_module = MagicMock()
        mock_log_instance = MagicMock()
        mock_log_module.Log.return_value = mock_log_instance

        # We need to make the "from .log import Log" fail
        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            # Fail the relative import of .log
            if level > 0 and fromlist and "Log" in fromlist:
                raise ImportError("Mocked import error for .log")
            return original_import(name, globals, locals, fromlist, level)

        with (
            patch("builtins.__import__", side_effect=mock_import),
            patch("importlib.util.spec_from_file_location", return_value=mock_spec) as mock_spec_func,
            patch("importlib.util.module_from_spec", return_value=mock_log_module) as mock_module_func,
        ):
            const._init_logger()

            # Verify the fallback path was used
            mock_spec_func.assert_called_once()
            call_args = mock_spec_func.call_args
            assert call_args[0][0] == "log"
            assert call_args[0][1] == expected_log_path

            mock_module_func.assert_called_once_with(mock_spec)
            mock_spec.loader.exec_module.assert_called_once_with(mock_log_module)
            assert const.LOGGER == mock_log_instance

    #
    # test_init_logger_fallback_raises_when_spec_is_none
    #
    def test_init_logger_fallback_raises_when_spec_is_none(self) -> None:
        """Test that _init_logger raises ImportError when spec is None.

        This tests the 'else: raise ImportError' branch in the fallback.
        """

        from custom_components.smart_cover_automation import const

        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level > 0 and fromlist and "Log" in fromlist:
                raise ImportError("Mocked import error for .log")
            return original_import(name, globals, locals, fromlist, level)

        with (
            patch("builtins.__import__", side_effect=mock_import),
            patch("importlib.util.spec_from_file_location", return_value=None),
        ):
            with pytest.raises(ImportError, match="Could not load log.py"):
                const._init_logger()

    #
    # test_init_logger_fallback_raises_when_loader_is_none
    #
    def test_init_logger_fallback_raises_when_loader_is_none(self) -> None:
        """Test that _init_logger raises ImportError when spec.loader is None.

        This tests the 'if spec and spec.loader' condition failing on loader.
        """

        from custom_components.smart_cover_automation import const

        mock_spec = MagicMock()
        mock_spec.loader = None

        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level > 0 and fromlist and "Log" in fromlist:
                raise ImportError("Mocked import error for .log")
            return original_import(name, globals, locals, fromlist, level)

        with (
            patch("builtins.__import__", side_effect=mock_import),
            patch("importlib.util.spec_from_file_location", return_value=mock_spec),
        ):
            with pytest.raises(ImportError, match="Could not load log.py"):
                const._init_logger()

    #
    # test_init_logger_normal_path
    #
    def test_init_logger_normal_path(self) -> None:
        """Test that _init_logger works normally when import succeeds."""

        from custom_components.smart_cover_automation import const
        from custom_components.smart_cover_automation.log import Log

        const._init_logger()

        assert isinstance(const.LOGGER, Log)
