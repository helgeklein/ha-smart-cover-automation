"""Tests for __init__ helpers and switch enabled logic via options."""

from __future__ import annotations

from typing import cast

import pytest

from custom_components.smart_cover_automation import async_get_options_flow
from custom_components.smart_cover_automation.data import IntegrationConfigEntry

from .conftest import MockConfigEntry, create_temperature_config


@pytest.mark.asyncio
async def test_async_get_options_flow_returns_handler() -> None:
    entry = MockConfigEntry(create_temperature_config())
    flow = await async_get_options_flow(cast(IntegrationConfigEntry, entry))
    # OptionsFlowHandler has async_step_init attribute
    assert hasattr(flow, "async_step_init")
