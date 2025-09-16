"""Edge cases and utility function tests.

This module contains tests for edge cases, utility functions, and special
scenarios in the DataUpdateCoordinator that don't fit into the main
automation logic categories.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from custom_components.smart_cover_automation.coordinator import (
    ConfigurationError,
    DataUpdateCoordinator,
)
from custom_components.smart_cover_automation.data import IntegrationConfigEntry
from tests.conftest import (
    TEST_DIRECT_AZIMUTH,
    MockConfigEntry,
)
from tests.coordinator.test_coordinator_base import TestDataUpdateCoordinatorBase


class TestEdgeCases(TestDataUpdateCoordinatorBase):
    """Test suite for edge cases and utility functions."""

    async def test_missing_config_keys_raise_configuration_error(
        self,
        mock_hass: MagicMock,
    ) -> None:
        """Test configuration validation with missing required keys.

        Validates that the coordinator properly validates configuration and
        raises ConfigurationError when required configuration keys are missing.
        This ensures proper setup validation during integration initialization.

        Test scenario:
        - Configuration: Missing required 'covers' key entirely
        - Expected behavior: ConfigurationError raised during initialization
        """
        # Build a config missing the required covers key entirely
        config: dict[str, Any] = {}
        config_entry = MockConfigEntry(config)
        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        await coordinator.async_refresh()
        assert isinstance(coordinator.last_exception, ConfigurationError)

    async def test_angle_calculation_utility(
        self,
        sun_coordinator: DataUpdateCoordinator,
    ) -> None:
        """Test angle difference calculation utility function.

        Validates the mathematical accuracy of the angle difference calculation
        utility used for determining if the sun is hitting windows. Tests
        include standard cases and edge cases like wraparound at 0°/360°.

        Test scenarios:
        - Direct alignment: 180° vs 180° = 0°
        - Standard difference: 180° vs 135° = 45°
        - Wraparound case: 0° vs 350° = 10° (not 350°)
        """
        # Test direct alignment (no difference)
        diff = sun_coordinator._calculate_angle_difference(TEST_DIRECT_AZIMUTH, TEST_DIRECT_AZIMUTH)
        assert diff == 0.0

        # Test standard 45-degree difference
        diff = sun_coordinator._calculate_angle_difference(TEST_DIRECT_AZIMUTH, 135.0)
        assert diff == 45.0

        # Test wraparound (0° and 350° should be 10° apart, not 350°)
        diff = sun_coordinator._calculate_angle_difference(0.0, 350.0)
        assert diff == 10.0

        # Test reverse wraparound
        diff = sun_coordinator._calculate_angle_difference(350.0, 0.0)
        assert diff == 10.0

        # Test maximum difference (180° apart)
        diff = sun_coordinator._calculate_angle_difference(0.0, 180.0)
        assert diff == 180.0
