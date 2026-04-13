"""Tests for persistent automation runtime state storage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.smart_cover_automation.automation_state_store import AutomationStateStore
from custom_components.smart_cover_automation.const import (
    DOMAIN,
    STORAGE_KEY_AUTOMATION_CLOSED_MARKERS,
    STORAGE_KEY_AUTOMATION_STATE,
    STORAGE_SAVE_DELAY_SECONDS,
    STORAGE_VERSION,
)


@pytest.fixture(autouse=True)
def clear_fallback_storage() -> None:
    """Isolate in-memory fallback state between tests."""

    AutomationStateStore._fallback_storage.clear()


class TestAutomationStateStore:
    """Test the storage wrapper around Home Assistant Store."""

    @staticmethod
    def _prepare_hass(mock_hass: MagicMock) -> MagicMock:
        """Populate the minimal Home Assistant attributes required by Store mode."""

        mock_hass.data = {}
        mock_hass.config = MagicMock()
        return mock_hass

    def test_init_creates_store_with_expected_key(self, mock_hass: MagicMock) -> None:
        """The persistent store should be created with the entry-specific storage key."""

        self._prepare_hass(mock_hass)

        with patch("custom_components.smart_cover_automation.automation_state_store.Store") as mock_store_class:
            AutomationStateStore(mock_hass, "entry_123")

        mock_store_class.assert_called_once_with(
            mock_hass,
            STORAGE_VERSION,
            f"{DOMAIN}.entry_123.{STORAGE_KEY_AUTOMATION_STATE}",
        )

    def test_schedule_save_uses_fallback_storage_when_hass_lacks_store_support(self) -> None:
        """Fallback mode should cache a copy of the markers in memory."""

        store = AutomationStateStore(object(), "entry_123")
        markers = {"cover.kitchen": "evening_close"}

        store.schedule_save_closed_markers(markers)
        markers["cover.kitchen"] = "mutated"

        assert AutomationStateStore._fallback_storage["entry_123"] == {"cover.kitchen": "evening_close"}

    @pytest.mark.asyncio
    async def test_load_returns_fallback_copy_when_store_is_unavailable(self) -> None:
        """Fallback loads should return a copy so callers cannot mutate shared state."""

        AutomationStateStore._fallback_storage["entry_123"] = {"cover.kitchen": "evening_close"}
        store = AutomationStateStore(object(), "entry_123")

        result = await store.async_load_closed_markers()
        result["cover.kitchen"] = "mutated"

        assert AutomationStateStore._fallback_storage["entry_123"] == {"cover.kitchen": "evening_close"}

    @pytest.mark.asyncio
    async def test_async_save_uses_fallback_storage_when_store_is_unavailable(self) -> None:
        """Immediate saves should update the fallback cache in mock environments."""

        store = AutomationStateStore(object(), "entry_123")

        await store.async_save_closed_markers({"cover.kitchen": "evening_close"})

        assert AutomationStateStore._fallback_storage["entry_123"] == {"cover.kitchen": "evening_close"}

    @pytest.mark.asyncio
    async def test_async_remove_uses_fallback_storage_when_store_is_unavailable(self) -> None:
        """Removal should delete only the targeted entry in fallback mode."""

        AutomationStateStore._fallback_storage["entry_123"] = {"cover.kitchen": "evening_close"}
        AutomationStateStore._fallback_storage["other_entry"] = {"cover.office": "manual"}
        store = AutomationStateStore(object(), "entry_123")

        await store.async_remove()

        assert "entry_123" not in AutomationStateStore._fallback_storage
        assert AutomationStateStore._fallback_storage["other_entry"] == {"cover.office": "manual"}

    def test_schedule_save_passes_snapshot_and_delay_to_store(self, mock_hass: MagicMock) -> None:
        """Delayed saves should persist a snapshot instead of a live mapping reference."""

        self._prepare_hass(mock_hass)

        delayed_payloads: list[dict[str, dict[str, str]]] = []

        def capture_payload(factory, delay: int) -> None:
            delayed_payloads.append(factory())
            assert delay == STORAGE_SAVE_DELAY_SECONDS

        mock_store = MagicMock()
        mock_store.async_delay_save.side_effect = capture_payload

        with patch("custom_components.smart_cover_automation.automation_state_store.Store", return_value=mock_store):
            store = AutomationStateStore(mock_hass, "entry_123")

        markers = {"cover.kitchen": "evening_close"}
        store.schedule_save_closed_markers(markers)
        markers["cover.kitchen"] = "mutated"

        assert delayed_payloads == [{STORAGE_KEY_AUTOMATION_CLOSED_MARKERS: {"cover.kitchen": "evening_close"}}]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "loaded_data, expected",
        [
            (None, {}),
            ([], {}),
            ({}, {}),
            ({STORAGE_KEY_AUTOMATION_CLOSED_MARKERS: []}, {}),
            (
                {
                    STORAGE_KEY_AUTOMATION_CLOSED_MARKERS: {
                        "cover.kitchen": "evening_close",
                        1: "bad_key",
                        "cover.office": None,
                    }
                },
                {"cover.kitchen": "evening_close"},
            ),
        ],
    )
    async def test_load_filters_invalid_persisted_data(
        self,
        mock_hass: MagicMock,
        loaded_data: object,
        expected: dict[str, str],
    ) -> None:
        """Loaded data should be validated before use."""

        self._prepare_hass(mock_hass)

        mock_store = MagicMock()
        mock_store.async_load = AsyncMock(return_value=loaded_data)

        with patch("custom_components.smart_cover_automation.automation_state_store.Store", return_value=mock_store):
            store = AutomationStateStore(mock_hass, "entry_123")

        assert await store.async_load_closed_markers() == expected

    @pytest.mark.asyncio
    async def test_async_save_passes_expected_payload_to_store(self, mock_hass: MagicMock) -> None:
        """Immediate saves should write the closed-marker payload to Store."""

        self._prepare_hass(mock_hass)

        mock_store = MagicMock()
        mock_store.async_save = AsyncMock()

        with patch("custom_components.smart_cover_automation.automation_state_store.Store", return_value=mock_store):
            store = AutomationStateStore(mock_hass, "entry_123")

        await store.async_save_closed_markers({"cover.kitchen": "evening_close"})

        mock_store.async_save.assert_awaited_once_with({STORAGE_KEY_AUTOMATION_CLOSED_MARKERS: {"cover.kitchen": "evening_close"}})

    @pytest.mark.asyncio
    async def test_async_remove_calls_store_remove(self, mock_hass: MagicMock) -> None:
        """Entry removal should remove the Home Assistant store file."""

        self._prepare_hass(mock_hass)

        mock_store = MagicMock()
        mock_store.async_remove = AsyncMock()

        with patch("custom_components.smart_cover_automation.automation_state_store.Store", return_value=mock_store):
            store = AutomationStateStore(mock_hass, "entry_123")

        await store.async_remove()

        mock_store.async_remove.assert_awaited_once_with()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method_name", "side_effect", "expected_message"),
        [
            ("async_load", OSError("load failed"), "Failed to load persisted automation state"),
            ("async_delay_save", TypeError("delay failed"), "Failed to schedule persisted automation state save"),
            ("async_save", ValueError("save failed"), "Failed to persist automation state"),
            ("async_remove", AttributeError("remove failed"), "Failed to remove persisted automation state"),
        ],
    )
    async def test_store_exceptions_are_logged_and_suppressed(
        self,
        mock_hass: MagicMock,
        method_name: str,
        side_effect: Exception,
        expected_message: str,
    ) -> None:
        """Storage helper failures should not escape the wrapper."""

        self._prepare_hass(mock_hass)

        mock_store = MagicMock()
        if method_name == "async_delay_save":
            setattr(mock_store, method_name, MagicMock(side_effect=side_effect))
        else:
            setattr(mock_store, method_name, AsyncMock(side_effect=side_effect))

        with (
            patch("custom_components.smart_cover_automation.automation_state_store.Store", return_value=mock_store),
            patch("custom_components.smart_cover_automation.automation_state_store.Log") as mock_log_class,
        ):
            mock_logger = MagicMock()
            mock_log_class.return_value = mock_logger
            store = AutomationStateStore(mock_hass, "entry_123")

            if method_name == "async_load":
                assert await store.async_load_closed_markers() == {}
            elif method_name == "async_delay_save":
                store.schedule_save_closed_markers({"cover.kitchen": "evening_close"})
            elif method_name == "async_save":
                await store.async_save_closed_markers({"cover.kitchen": "evening_close"})
            else:
                await store.async_remove()

        mock_logger.warning.assert_called_once()
        warning_args = mock_logger.warning.call_args.args
        assert warning_args[0] == f"{expected_message}: %s"
        assert warning_args[1] == side_effect
