"""Base test classes and shared fixtures for coordinator tests.

This module provides the base test class and shared fixtures that are inherited
by all coordinator test modules. It establishes common setup for testing
DataUpdateCoordinator functionality across different test categories.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    MockConfigEntry,
    create_sun_config,
    create_temperature_config,
)


class TestDataUpdateCoordinatorBase:
    """Base test class for DataUpdateCoordinator with shared fixtures and initialization tests."""

    @pytest.fixture
    def coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a DataUpdateCoordinator instance configured for temperature automation.

        Returns a coordinator with basic temperature automation configuration
        for testing temperature-based cover control logic.
        """
        config = create_temperature_config()
        config_entry = MockConfigEntry(config)
        return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

    @pytest.fixture
    def sun_coordinator(self, mock_hass: MagicMock) -> DataUpdateCoordinator:
        """Create a DataUpdateCoordinator instance configured for sun automation.

        Returns a coordinator with sun automation configuration for testing
        sun-based cover control logic including azimuth and elevation thresholds.
        """
        config = create_sun_config()
        config_entry = MockConfigEntry(config)
        return DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

    async def test_init(self, coordinator: DataUpdateCoordinator) -> None:
        """Test basic coordinator initialization and configuration parsing.

        Validates that the DataUpdateCoordinator properly initializes with
        configuration data and sets up the required attributes and state
        for automation processing.
        """
        assert coordinator is not None
        assert coordinator.data is None  # No data until first refresh
        assert coordinator.last_exception is None  # No errors initially


# Test class inheritance examples for each test category
class TestTemperatureAutomation(TestDataUpdateCoordinatorBase):
    """Test class for temperature automation tests (inherits shared fixtures)."""

    pass


class TestSunAutomation(TestDataUpdateCoordinatorBase):
    """Test class for sun automation tests (inherits shared fixtures)."""

    pass


class TestCombinedAutomation(TestDataUpdateCoordinatorBase):
    """Test class for combined automation tests (inherits shared fixtures)."""

    pass


class TestErrorHandling(TestDataUpdateCoordinatorBase):
    """Test class for error handling tests (inherits shared fixtures)."""

    pass


class TestEdgeCases(TestDataUpdateCoordinatorBase):
    """Test class for edge case tests (inherits shared fixtures)."""

    pass
