"""Tests for unique ID migration in Smart Cover Automation integration.

This module contains comprehensive tests for the _async_migrate_unique_ids function
that handles migrating legacy unique IDs from the old format ({DOMAIN}_{key}) to
the new format ({entry_id}_{key}). This migration enables multi-instance support
while preserving user-facing entity_ids.

Key testing areas include:
1. **No Migration Needed**: Tests early return when no legacy entities exist
2. **Successful Migration**: Tests single and multiple entity migrations
3. **Collision Handling**: Tests orphan removal and retry logic
4. **Error Recovery**: Tests handling of various error conditions
5. **Edge Cases**: Tests unusual but valid scenarios
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.smart_cover_automation import _async_migrate_unique_ids, const


class TestAsyncMigrateUniqueIds:
    """Test suite for the _async_migrate_unique_ids function.

    This test class validates the unique ID migration logic that converts
    legacy unique IDs to the new entry-based format for multi-instance support.
    """

    @pytest.fixture
    def mock_hass(self) -> MagicMock:
        """Create a mock Home Assistant instance for migration tests."""

        hass = MagicMock()
        hass.data = {}
        return hass

    @pytest.fixture
    def mock_entry(self) -> MagicMock:
        """Create a mock config entry for migration tests."""

        entry = MagicMock()
        entry.entry_id = "abc123def456"
        entry.domain = const.DOMAIN
        return entry

    @pytest.fixture
    def mock_registry(self) -> MagicMock:
        """Create a mock entity registry."""

        registry = MagicMock()
        registry.async_update_entity = MagicMock()
        registry.async_remove = MagicMock()
        registry.async_get = MagicMock(return_value=None)
        registry.async_get_entity_id = MagicMock(return_value=None)
        return registry

    #
    # test_no_entities_need_migration_returns_early
    #
    async def test_no_entities_need_migration_returns_early(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that migration returns early when no legacy entities exist.

        When all entities already use the new format (entry_id based unique IDs),
        the migration should return without logging or making any registry updates.
        """
        import logging

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Create entities with new format unique IDs (no migration needed)
        new_format_entity = MagicMock()
        new_format_entity.unique_id = f"{mock_entry.entry_id}_status"
        new_format_entity.entity_id = "binary_sensor.smart_cover_automation_status"

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[new_format_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Should not attempt any updates
        mock_registry.async_update_entity.assert_not_called()

        # Should not log migration messages
        assert "Starting unique ID migration" not in caplog.text

    #
    # test_no_entities_at_all_returns_early
    #
    async def test_no_entities_at_all_returns_early(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that migration returns early when no entities exist for the config entry."""
        import logging

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        mock_registry.async_update_entity.assert_not_called()
        assert "Starting unique ID migration" not in caplog.text

    #
    # test_successful_migration_single_entity
    #
    async def test_successful_migration_single_entity(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test successful migration of a single entity.

        Verifies that a legacy unique ID is correctly transformed to the new format
        and the registry is updated appropriately.
        """
        import logging

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Create entity with legacy format
        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_status"
        legacy_entity.entity_id = "binary_sensor.smart_cover_automation_status"
        legacy_entity.platform = const.DOMAIN

        expected_new_unique_id = f"{mock_entry.entry_id}_status"

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Verify update was called with correct parameters
        mock_registry.async_update_entity.assert_called_once_with(
            legacy_entity.entity_id,
            new_unique_id=expected_new_unique_id,
        )

        # Verify logging
        assert "Starting unique ID migration" in caplog.text
        assert "Found 1 entities to migrate" in caplog.text
        assert "Migrated 1 entities" in caplog.text

    #
    # test_successful_migration_multiple_entities
    #
    async def test_successful_migration_multiple_entities(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test successful migration of multiple entities."""
        import logging

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Create multiple entities with legacy format
        entity1 = MagicMock()
        entity1.unique_id = f"{const.DOMAIN}_status"
        entity1.entity_id = "binary_sensor.smart_cover_automation_status"
        entity1.platform = const.DOMAIN

        entity2 = MagicMock()
        entity2.unique_id = f"{const.DOMAIN}_enabled"
        entity2.entity_id = "switch.smart_cover_automation_enabled"
        entity2.platform = const.DOMAIN

        entity3 = MagicMock()
        entity3.unique_id = f"{const.DOMAIN}_sun_azimuth"
        entity3.entity_id = "sensor.smart_cover_automation_sun_azimuth"
        entity3.platform = const.DOMAIN

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[entity1, entity2, entity3],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Verify all three entities were updated
        assert mock_registry.async_update_entity.call_count == 3
        assert "Found 3 entities to migrate" in caplog.text
        assert "Migrated 3 entities" in caplog.text

    #
    # test_mixed_entities_only_legacy_migrated
    #
    async def test_mixed_entities_only_legacy_migrated(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that only legacy format entities are migrated.

        When a mix of legacy and new format entities exist, only the legacy
        ones should be processed for migration.
        """
        import logging

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        # Legacy format entity
        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_status"
        legacy_entity.entity_id = "binary_sensor.smart_cover_automation_status"
        legacy_entity.platform = const.DOMAIN

        # New format entity (should be skipped)
        new_entity = MagicMock()
        new_entity.unique_id = f"{mock_entry.entry_id}_enabled"
        new_entity.entity_id = "switch.smart_cover_automation_enabled"
        new_entity.platform = const.DOMAIN

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity, new_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Only the legacy entity should be updated
        assert mock_registry.async_update_entity.call_count == 1
        mock_registry.async_update_entity.assert_called_once_with(
            legacy_entity.entity_id,
            new_unique_id=f"{mock_entry.entry_id}_status",
        )
        assert "Found 1 entities to migrate" in caplog.text

    #
    # test_collision_with_orphan_removes_and_retries
    #
    async def test_collision_with_orphan_removes_and_retries(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test collision detection and orphan removal.

        When a collision is detected with an orphaned entity (no config_entry_id),
        the orphan should be removed and migration retried successfully.
        """
        import logging

        caplog.set_level(logging.WARNING, logger="custom_components.smart_cover_automation")

        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_status"
        legacy_entity.entity_id = "binary_sensor.smart_cover_automation_status"
        legacy_entity.platform = const.DOMAIN

        # Orphaned entity blocking the new unique ID
        orphan_entity = MagicMock()
        orphan_entity.config_entry_id = None  # Orphan indicator

        blocking_entity_id = "binary_sensor.old_orphan_status"

        # First call raises ValueError (collision), second succeeds
        mock_registry.async_update_entity.side_effect = [
            ValueError("unique_id already exists"),
            None,  # Retry succeeds
        ]
        mock_registry.async_get_entity_id.return_value = blocking_entity_id
        mock_registry.async_get.return_value = orphan_entity

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Verify orphan was removed
        mock_registry.async_remove.assert_called_once_with(blocking_entity_id)

        # Verify retry was attempted
        assert mock_registry.async_update_entity.call_count == 2

        # Verify logging
        assert "Collision detected" in caplog.text
        assert "Found orphaned entity" in caplog.text
        assert "Removing it" in caplog.text

    #
    # test_collision_retry_fails
    #
    async def test_collision_retry_fails(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test collision retry failure.

        When an orphan is removed but the retry still fails, an error should be logged.
        """
        import logging

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_status"
        legacy_entity.entity_id = "binary_sensor.smart_cover_automation_status"
        legacy_entity.platform = const.DOMAIN

        orphan_entity = MagicMock()
        orphan_entity.config_entry_id = None

        blocking_entity_id = "binary_sensor.old_orphan_status"

        # Both attempts fail
        mock_registry.async_update_entity.side_effect = [
            ValueError("unique_id already exists"),
            ValueError("still exists"),  # Retry also fails
        ]
        mock_registry.async_get_entity_id.return_value = blocking_entity_id
        mock_registry.async_get.return_value = orphan_entity

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        assert "Migration retry failed" in caplog.text
        assert "Migrated 0 entities" in caplog.text

    #
    # test_collision_with_real_conflict
    #
    async def test_collision_with_real_conflict(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test collision with a real (non-orphan) entity.

        When a collision occurs with an entity that has a valid config_entry_id,
        it cannot be auto-resolved and should be logged as a warning.
        """
        import logging

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_status"
        legacy_entity.entity_id = "binary_sensor.smart_cover_automation_status"
        legacy_entity.platform = const.DOMAIN

        # Real entity (not orphan) blocking the new unique ID
        real_entity = MagicMock()
        real_entity.config_entry_id = "other_entry_id"  # Has a config entry

        blocking_entity_id = "binary_sensor.other_instance_status"

        mock_registry.async_update_entity.side_effect = ValueError("unique_id already exists")
        mock_registry.async_get_entity_id.return_value = blocking_entity_id
        mock_registry.async_get.return_value = real_entity

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Should NOT remove the real entity
        mock_registry.async_remove.assert_not_called()

        # Should log the collision but not as orphan removal
        assert "Collision detected" in caplog.text
        assert "Error migrating unique_id" in caplog.text
        assert "Migrated 0 entities" in caplog.text

    #
    # test_collision_no_blocking_entity_found
    #
    async def test_collision_no_blocking_entity_found(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test collision when blocking entity cannot be found in registry.

        This edge case occurs when the collision error is raised but
        async_get_entity_id returns None.
        """
        import logging

        caplog.set_level(logging.WARNING, logger="custom_components.smart_cover_automation")

        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_status"
        legacy_entity.entity_id = "binary_sensor.smart_cover_automation_status"
        legacy_entity.platform = const.DOMAIN

        mock_registry.async_update_entity.side_effect = ValueError("unique_id already exists")
        mock_registry.async_get_entity_id.return_value = None  # Cannot find blocking entity

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Should log the unusual situation
        assert "collision detected" in caplog.text.lower()
        assert "no blocking entity found" in caplog.text.lower()

    #
    # test_unexpected_exception_during_migration
    #
    async def test_unexpected_exception_during_migration(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test handling of unexpected exceptions during migration.

        Non-ValueError exceptions should be caught and logged as errors.
        """
        import logging

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_status"
        legacy_entity.entity_id = "binary_sensor.smart_cover_automation_status"
        legacy_entity.platform = const.DOMAIN

        mock_registry.async_update_entity.side_effect = RuntimeError("Unexpected error")

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Should log the unexpected error
        assert "Unexpected error migrating" in caplog.text
        assert "Migrated 0 entities" in caplog.text

    #
    # test_extracts_key_correctly_from_legacy_id
    #
    async def test_extracts_key_correctly_from_legacy_id(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
    ) -> None:
        """Test that the key is correctly extracted from legacy unique IDs.

        The migration should handle keys that contain underscores correctly,
        only removing the domain prefix once.
        """
        # Legacy format with underscores in key
        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_sun_azimuth_sensor"
        legacy_entity.entity_id = "sensor.smart_cover_automation_sun_azimuth"
        legacy_entity.platform = const.DOMAIN

        expected_new_unique_id = f"{mock_entry.entry_id}_sun_azimuth_sensor"

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        mock_registry.async_update_entity.assert_called_once_with(
            legacy_entity.entity_id,
            new_unique_id=expected_new_unique_id,
        )

    #
    # test_partial_migration_on_mixed_success
    #
    async def test_partial_migration_on_mixed_success(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that partial migration counts are logged correctly.

        When some entities migrate successfully and others fail,
        the count should reflect only successful migrations.
        """
        import logging

        caplog.set_level(logging.INFO, logger="custom_components.smart_cover_automation")

        entity1 = MagicMock()
        entity1.unique_id = f"{const.DOMAIN}_status"
        entity1.entity_id = "binary_sensor.smart_cover_automation_status"
        entity1.platform = const.DOMAIN

        entity2 = MagicMock()
        entity2.unique_id = f"{const.DOMAIN}_enabled"
        entity2.entity_id = "switch.smart_cover_automation_enabled"
        entity2.platform = const.DOMAIN

        entity3 = MagicMock()
        entity3.unique_id = f"{const.DOMAIN}_sun_azimuth"
        entity3.entity_id = "sensor.smart_cover_automation_sun_azimuth"
        entity3.platform = const.DOMAIN

        # First succeeds, second fails with unresolvable collision, third succeeds
        mock_registry.async_update_entity.side_effect = [
            None,  # Success
            ValueError("collision"),  # Fail
            None,  # Success
        ]
        mock_registry.async_get_entity_id.return_value = None  # No blocking entity found

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[entity1, entity2, entity3],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        assert "Found 3 entities to migrate" in caplog.text
        assert "Migrated 2 entities" in caplog.text

    #
    # test_entity_domain_extracted_from_entity_id
    #
    async def test_entity_domain_extracted_from_entity_id(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
    ) -> None:
        """Test that entity domain is correctly extracted from entity_id.

        The collision resolution logic extracts the domain (e.g., 'binary_sensor')
        from the entity_id for registry lookup.
        """
        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_status"
        legacy_entity.entity_id = "binary_sensor.smart_cover_automation_status"
        legacy_entity.platform = const.DOMAIN

        orphan = MagicMock()
        orphan.config_entry_id = None

        mock_registry.async_update_entity.side_effect = [ValueError("collision"), None]
        mock_registry.async_get.return_value = orphan

        # Capture the call to async_get_entity_id to verify domain extraction
        mock_registry.async_get_entity_id.return_value = "binary_sensor.old_status"

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Verify async_get_entity_id was called with correct domain
        mock_registry.async_get_entity_id.assert_called_with(
            "binary_sensor",  # Extracted from entity_id
            legacy_entity.platform,
            f"{mock_entry.entry_id}_status",
        )

    #
    # test_different_entity_platforms
    #
    @pytest.mark.parametrize(
        ("entity_id", "expected_domain"),
        [
            ("binary_sensor.sca_status", "binary_sensor"),
            ("switch.sca_enabled", "switch"),
            ("sensor.sca_sun_azimuth", "sensor"),
            ("select.sca_lock_mode", "select"),
            ("number.sca_temp_threshold", "number"),
        ],
    )
    async def test_different_entity_platforms(
        self,
        mock_hass: MagicMock,
        mock_entry: MagicMock,
        mock_registry: MagicMock,
        entity_id: str,
        expected_domain: str,
    ) -> None:
        """Test migration works for all entity platform types."""

        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_test_key"
        legacy_entity.entity_id = entity_id
        legacy_entity.platform = const.DOMAIN

        orphan = MagicMock()
        orphan.config_entry_id = None

        mock_registry.async_update_entity.side_effect = [ValueError("collision"), None]
        mock_registry.async_get.return_value = orphan
        mock_registry.async_get_entity_id.return_value = f"{expected_domain}.blocking_entity"

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, mock_entry)

        # Verify domain was correctly extracted
        mock_registry.async_get_entity_id.assert_called_with(
            expected_domain,
            const.DOMAIN,
            f"{mock_entry.entry_id}_test_key",
        )

    #
    # test_short_entry_id
    #
    async def test_short_entry_id(
        self,
        mock_hass: MagicMock,
        mock_registry: MagicMock,
    ) -> None:
        """Test migration with a short entry_id."""

        entry = MagicMock()
        entry.entry_id = "abc"  # Short entry ID
        entry.domain = const.DOMAIN

        legacy_entity = MagicMock()
        legacy_entity.unique_id = f"{const.DOMAIN}_status"
        legacy_entity.entity_id = "binary_sensor.smart_cover_automation_status"
        legacy_entity.platform = const.DOMAIN

        with (
            patch(
                "custom_components.smart_cover_automation.er.async_get",
                return_value=mock_registry,
            ),
            patch(
                "custom_components.smart_cover_automation.er.async_entries_for_config_entry",
                return_value=[legacy_entity],
            ),
        ):
            await _async_migrate_unique_ids(mock_hass, entry)

        mock_registry.async_update_entity.assert_called_once_with(
            legacy_entity.entity_id,
            new_unique_id="abc_status",
        )
