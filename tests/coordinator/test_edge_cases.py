"""Edge cases and utility function tests.

This module contains tests for edge cases, utility functions, and special
scenarios in the DataUpdateCoordinator that don't fit into the main
automation logic categories.
"""

from __future__ import annotations

import logging
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from custom_components.smart_cover_automation.config import ConfKeys
from custom_components.smart_cover_automation.coordinator import (
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
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test graceful configuration validation with missing required keys.

        Validates that the coordinator gracefully handles configuration validation
        and reports errors when required configuration keys are missing. The system
        should log the error but continue operation with minimal state to keep
        integration entities available.

        Test scenario:
        - Configuration: Missing required 'covers' key entirely
        - Expected behavior: Error logged, minimal state returned, no exception raised
        """
        # Build a config missing the required covers key entirely
        config: dict[str, Any] = {}
        config_entry = MockConfigEntry(config)

        # Set caplog to capture warning level messages
        caplog.set_level(logging.WARNING, logger="custom_components.smart_cover_automation")

        coordinator = DataUpdateCoordinator(mock_hass, cast(IntegrationConfigEntry, config_entry))

        await coordinator.async_refresh()

        # Verify graceful error handling
        assert coordinator.last_exception is None  # No exception should propagate
        assert coordinator.data == {
            ConfKeys.COVERS.value: {},
            "message": "No covers configured; skipping actions",
        }  # Minimal valid state returned

    async def test_angle_calculation_utility(
        self,
        sun_coordinator: DataUpdateCoordinator,
    ) -> None:
        """Test angle difference calculation utility function.

        Validates the mathematical accuracy of the angle difference calculation
        utility used for determining if the sun is hitting windows. Tests
        include comprehensive edge cases like wraparound at 0°/360°.

        Test scenarios:
        - Direct alignment: 180° vs 180° = 0°
        - Standard difference: 180° vs 135° = 45°
        - Wraparound case: 0° vs 350° = 10° (not 350°)
        - Reverse wraparound: 350° vs 0° = 10°
        - Maximum difference: 0° vs 180° = 180°
        """
        from custom_components.smart_cover_automation.automation_engine import CoverAutomation

        # Test direct alignment (no difference)
        diff = CoverAutomation._calculate_angle_difference(TEST_DIRECT_AZIMUTH, TEST_DIRECT_AZIMUTH)
        assert diff == 0.0

        # Test standard 45-degree difference
        diff = CoverAutomation._calculate_angle_difference(TEST_DIRECT_AZIMUTH, 135.0)
        assert diff == 45.0

        # Test wraparound (0° and 350° should be 10° apart, not 350°)
        diff = CoverAutomation._calculate_angle_difference(0.0, 350.0)
        assert diff == 10.0

        # Test reverse wraparound
        diff = CoverAutomation._calculate_angle_difference(350.0, 0.0)
        assert diff == 10.0

        # Test maximum difference (180° apart)
        diff = CoverAutomation._calculate_angle_difference(0.0, 180.0)
        assert diff == 180.0
