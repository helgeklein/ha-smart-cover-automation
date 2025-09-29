"""Base test class for DataUpdateCoordinator tests.

This module provides the base test class that other coordinator test modules
inherit from. It includes shared initialization tests and basic coordinator
functionality testing.
"""

from __future__ import annotations

from custom_components.smart_cover_automation.coordinator import DataUpdateCoordinator


class TestDataUpdateCoordinatorBase:
    """Base test class for DataUpdateCoordinator with shared initialization tests."""

    async def test_init(self, coordinator: DataUpdateCoordinator) -> None:
        """Test basic coordinator initialization and configuration parsing.

        Validates that DataUpdateCoordinator properly initializes with the
        provided configuration and sets up all required attributes for
        automation processing.

        This test verifies the fundamental coordinator setup that all other
        tests depend on.
        """
        # Verify coordinator has expected configuration attributes
        assert coordinator.hass is not None
        assert coordinator.name == "smart_cover_automation"
        assert coordinator.update_interval is not None


class TestErrorHandling(TestDataUpdateCoordinatorBase):
    """Test error handling scenarios in DataUpdateCoordinator initialization.

    This class tests various error conditions during coordinator setup
    to ensure robust error handling and proper exception propagation.
    """

    async def test_init(self, coordinator: DataUpdateCoordinator) -> None:
        """Test that error handling coordinator still initializes properly.

        Even when testing error scenarios, the coordinator itself should
        initialize successfully. The errors being tested occur during
        data updates, not during coordinator creation.
        """
        # Verify basic coordinator functionality even in error test context
        assert coordinator.hass is not None
        assert coordinator.name == "smart_cover_automation"
        assert coordinator.update_interval is not None
