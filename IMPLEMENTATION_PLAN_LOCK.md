# Implementation Plan: Cover Lock Feature

## Overview
Add global cover locking functionality with three modes: hold position, force open, and force close. Implements a hybrid approach with service + select entity for maximum flexibility.

## Requirements
- ✅ Global lock (affects all covers)
- ✅ No timeout (manual unlock required)
- ✅ Let movements finish (don't interrupt ongoing operations)
- ✅ Service-based control (primary interface)
- ✅ Re-evaluate covers during each automation run while locked
- ✅ Force covers to target position even when locked

## Lock Modes

```python
class LockMode(Enum):
    UNLOCKED = "unlocked"              # Normal automation (default)
    HOLD_POSITION = "hold_position"    # Prevent any movement
    FORCE_OPEN = "force_open"          # Open to 100% and prevent automation
    FORCE_CLOSE = "force_close"        # Close to 0% and prevent automation
```

## Architecture Changes

### 1. Constants (`const.py`)

**Add new constants:**
```python
# Lock mode constants
LOCK_MODE_UNLOCKED: Final[str] = "unlocked"
LOCK_MODE_HOLD_POSITION: Final[str] = "hold_position"
LOCK_MODE_FORCE_OPEN: Final[str] = "force_open"
LOCK_MODE_FORCE_CLOSE: Final[str] = "force_close"

# Service constants
SERVICE_SET_LOCK: Final[str] = "set_lock"
SERVICE_FIELD_LOCK_MODE: Final[str] = "lock_mode"

# Config key for lock state
LOCK_MODE_STATE: Final[str] = "lock_mode_state"

# Sensor/Select keys
SELECT_KEY_LOCK_MODE: Final[str] = "lock_mode"
SENSOR_KEY_LOCK_ACTIVE: Final[str] = "lock_active"

# Cover attribute for lock state
COVER_ATTR_LOCK_MODE: Final[str] = "cover_lock_mode"
COVER_ATTR_LOCK_ACTIVE: Final[str] = "cover_lock_active"
```

### 2. Configuration (`config.py`)

**Add to ConfKeys:**
```python
LOCK_MODE: ConfKey = ConfKey(
    "lock_mode",
    default=LOCK_MODE_UNLOCKED,
    spec=vol.In([
        LOCK_MODE_UNLOCKED,
        LOCK_MODE_HOLD_POSITION,
        LOCK_MODE_FORCE_OPEN,
        LOCK_MODE_FORCE_CLOSE,
    ]),
)
```

**Add to ResolvedConfig:**
```python
@dataclass
class ResolvedConfig:
    # ... existing fields ...
    lock_mode: str  # Current lock mode
```

### 3. Coordinator (`coordinator.py`)

**Add lock state management:**
```python
class DataUpdateCoordinator(BaseCoordinator[CoordinatorData]):

    def __init__(self, ...):
        # ... existing init ...

        # Initialize lock state from config
        self._lock_mode: str = resolved.lock_mode
        self._lock_activated_at: datetime | None = None  # When lock was activated

    @property
    def lock_mode(self) -> str:
        """Get current lock mode."""
        return self._lock_mode

    @property
    def is_locked(self) -> bool:
        """Check if covers are locked (any mode except unlocked)."""
        return self._lock_mode != LOCK_MODE_UNLOCKED

    async def async_set_lock_mode(self, lock_mode: str) -> None:
        """Set the lock mode and persist to config.

        Args:
            lock_mode: One of LOCK_MODE_* constants

        This method:
        1. Updates internal state
        2. Persists to config options
        3. Triggers immediate coordinator refresh
        4. Logs the change
        """
        old_mode = self._lock_mode
        self._lock_mode = lock_mode

        # Update timestamp when locking/unlocking
        if lock_mode == LOCK_MODE_UNLOCKED:
            self._lock_activated_at = None
            const.LOGGER.info(f"Lock deactivated (was: {old_mode})")
        else:
            self._lock_activated_at = datetime.now(timezone.utc)
            const.LOGGER.warning(f"Lock activated: {lock_mode} (was: {old_mode})")

        # Persist to config
        await self._async_persist_option(ConfKeys.LOCK_MODE.value, lock_mode)

        # Trigger immediate refresh to apply lock state
        await self.async_request_refresh()
```

### 4. Automation Engine (`automation_engine.py`)

**Modify `run()` method to pass lock state:**
```python
async def run(self, cover_states: dict[str, State | None]) -> CoordinatorData:
    """Execute the automation logic for all covers."""

    # ... existing checks ...

    # Get current lock state from coordinator
    lock_mode = self.resolved.lock_mode
    is_locked = lock_mode != const.LOCK_MODE_UNLOCKED

    # Store lock state in result for sensors
    result["lock_mode"] = lock_mode
    result["lock_active"] = is_locked

    # Log lock state if active
    if is_locked:
        const.LOGGER.warning(f"Cover lock active: {lock_mode}")

    # Process each cover (pass lock_mode to CoverAutomation)
    for entity_id, state in cover_states.items():
        cover_automation = CoverAutomation(
            entity_id=entity_id,
            resolved=self.resolved,
            config=self.config,
            cover_pos_history_mgr=self._cover_pos_history_mgr,
            ha_interface=self._ha_interface,
            lock_mode=lock_mode,  # NEW: Pass lock mode
        )
        cover_attrs = await cover_automation.process(state, sensor_data)
        if cover_attrs:
            result[ConfKeys.COVERS.value][entity_id] = cover_attrs

    return result
```

### 5. Cover Automation (`cover_automation.py`)

**Major changes to handle lock modes:**

```python
class CoverAutomation:

    def __init__(
        self,
        entity_id: str,
        resolved: ResolvedConfig,
        config: dict[str, Any],
        cover_pos_history_mgr: CoverPositionHistoryManager,
        ha_interface: Any,
        lock_mode: str,  # NEW parameter
    ) -> None:
        # ... existing init ...
        self._lock_mode = lock_mode

    async def process(self, state: State | None, sensor_data: SensorData) -> dict[str, Any]:
        """Process automation for this cover."""

        cover_attrs: dict[str, Any] = {}

        # ... existing validation ...

        # Add lock state to attributes
        cover_attrs[const.COVER_ATTR_LOCK_MODE] = self._lock_mode
        cover_attrs[const.COVER_ATTR_LOCK_ACTIVE] = self._lock_mode != const.LOCK_MODE_UNLOCKED

        # Check if cover is moving - ALWAYS skip if moving (let it finish)
        if self._is_cover_moving(state):
            const.LOGGER.debug(f"{self.entity_id}: Cover is moving, skipping (lock_mode={self._lock_mode})")
            return cover_attrs

        # ... get cover position ...

        # Handle lock modes BEFORE normal automation logic
        if self._lock_mode != const.LOCK_MODE_UNLOCKED:
            return await self._process_locked_cover(state, cover_attrs, current_pos, features)

        # Normal automation logic (only if unlocked)
        # ... existing process logic ...

    async def _process_locked_cover(
        self,
        state: State,
        cover_attrs: dict[str, Any],
        current_pos: int,
        features: int,
    ) -> dict[str, Any]:
        """Process cover when lock is active.

        This method enforces the lock mode by:
        1. HOLD_POSITION: Do nothing, skip automation
        2. FORCE_OPEN: Ensure cover is at 100%, move if not
        3. FORCE_CLOSE: Ensure cover is at 0%, move if not

        Args:
            state: Current cover state
            cover_attrs: Cover attributes dict to populate
            current_pos: Current cover position
            features: Cover supported features

        Returns:
            Updated cover_attrs dict
        """

        if self._lock_mode == const.LOCK_MODE_HOLD_POSITION:
            # HOLD_POSITION: Just block all automation
            const.LOGGER.info(f"{self.entity_id}: Lock active (HOLD_POSITION), skipping automation")
            cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] = current_pos
            cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] = current_pos
            self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
            return cover_attrs

        elif self._lock_mode == const.LOCK_MODE_FORCE_OPEN:
            # FORCE_OPEN: Ensure cover is fully open (100%)
            target_pos = const.COVER_POS_FULLY_OPEN

            if current_pos == target_pos:
                const.LOGGER.info(f"{self.entity_id}: Lock active (FORCE_OPEN), already at target position {target_pos}%")
                cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] = target_pos
                cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] = target_pos
                self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
            else:
                const.LOGGER.warning(f"{self.entity_id}: Lock active (FORCE_OPEN), moving to target position {target_pos}%")
                cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] = target_pos
                cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] = target_pos

                # Move cover to target position
                await self._move_cover(target_pos, features)
                self._cover_pos_history_mgr.add(self.entity_id, target_pos, cover_moved=True)

            return cover_attrs

        elif self._lock_mode == const.LOCK_MODE_FORCE_CLOSE:
            # FORCE_CLOSE: Ensure cover is fully closed (0%)
            target_pos = const.COVER_POS_FULLY_CLOSED

            if current_pos == target_pos:
                const.LOGGER.info(f"{self.entity_id}: Lock active (FORCE_CLOSE), already at target position {target_pos}%")
                cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] = target_pos
                cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] = target_pos
                self._cover_pos_history_mgr.add(self.entity_id, current_pos, cover_moved=False)
            else:
                const.LOGGER.warning(f"{self.entity_id}: Lock active (FORCE_CLOSE), moving to target position {target_pos}%")
                cover_attrs[const.COVER_ATTR_POS_TARGET_DESIRED] = target_pos
                cover_attrs[const.COVER_ATTR_POS_TARGET_FINAL] = target_pos

                # Move cover to target position
                await self._move_cover(target_pos, features)
                self._cover_pos_history_mgr.add(self.entity_id, target_pos, cover_moved=True)

            return cover_attrs

        else:
            # Should never reach here, but handle gracefully
            const.LOGGER.error(f"{self.entity_id}: Unknown lock mode: {self._lock_mode}")
            return cover_attrs
```

### 6. Service Registration (`__init__.py`)

**Add service registration in `async_setup_entry()`:**

```python
async def async_setup_entry(hass: HomeAssistant, entry: IntegrationConfigEntry) -> bool:
    """Set up integration from a config entry."""

    # ... existing setup ...

    # Register services
    await _async_register_services(hass, coordinator)

    # ... rest of setup ...

async def _async_register_services(hass: HomeAssistant, coordinator: DataUpdateCoordinator) -> None:
    """Register integration services.

    Args:
        hass: Home Assistant instance
        coordinator: The coordinator instance
    """
    import voluptuous as vol
    from homeassistant.helpers import config_validation as cv

    async def async_handle_set_lock(call: ServiceCall) -> None:
        """Handle set_lock service call.

        Args:
            call: Service call with lock_mode parameter
        """
        lock_mode = call.data[const.SERVICE_FIELD_LOCK_MODE]

        const.LOGGER.info(f"Service call: set_lock(lock_mode={lock_mode})")

        # Validate lock mode
        valid_modes = [
            const.LOCK_MODE_UNLOCKED,
            const.LOCK_MODE_HOLD_POSITION,
            const.LOCK_MODE_FORCE_OPEN,
            const.LOCK_MODE_FORCE_CLOSE,
        ]

        if lock_mode not in valid_modes:
            const.LOGGER.error(f"Invalid lock mode: {lock_mode}. Valid modes: {valid_modes}")
            raise ValueError(f"Invalid lock mode: {lock_mode}")

        # Apply lock mode via coordinator
        await coordinator.async_set_lock_mode(lock_mode)

    # Define service schema
    set_lock_schema = vol.Schema({
        vol.Required(const.SERVICE_FIELD_LOCK_MODE): cv.string,
    })

    # Register service
    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_SET_LOCK,
        async_handle_set_lock,
        schema=set_lock_schema,
    )

    const.LOGGER.info("Services registered")
```

### 7. Service Definition (`services.yaml`)

**Create new file:**

```yaml
set_lock:
  name: Set Cover Lock
  description: >
    Lock all covers in a specific state to prevent automation from moving them.
    Useful for weather emergencies (hail, storms) or manual override scenarios.
  fields:
    lock_mode:
      name: Lock Mode
      description: How to lock the covers
      required: true
      example: "force_close"
      selector:
        select:
          options:
            - label: "Unlocked (normal automation)"
              value: "unlocked"
            - label: "Hold current position"
              value: "hold_position"
            - label: "Force open and lock"
              value: "force_open"
            - label: "Force close and lock"
              value: "force_close"
```

### 8. Select Entity (`select.py` - NEW FILE)

**Create select platform for UI control:**

```python
"""Select platform for smart_cover_automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory

from .const import (
    DOMAIN,
    LOCK_MODE_FORCE_CLOSE,
    LOCK_MODE_FORCE_OPEN,
    LOCK_MODE_HOLD_POSITION,
    LOCK_MODE_UNLOCKED,
    SELECT_KEY_LOCK_MODE,
)
from .entity import IntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator = entry.runtime_data.coordinator

    entities = [
        LockModeSelect(coordinator),
    ]

    async_add_entities(entities)


class IntegrationSelect(IntegrationEntity, SelectEntity):
    """Base select entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SelectEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{DOMAIN}_{entity_description.key}"


class LockModeSelect(IntegrationSelect):
    """Select entity for choosing lock mode."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(
            coordinator,
            SelectEntityDescription(
                key=SELECT_KEY_LOCK_MODE,
                name="Lock Mode",
                icon="mdi:lock",
                entity_category=EntityCategory.CONFIG,
            ),
        )

        self._attr_options = [
            LOCK_MODE_UNLOCKED,
            LOCK_MODE_HOLD_POSITION,
            LOCK_MODE_FORCE_OPEN,
            LOCK_MODE_FORCE_CLOSE,
        ]

    @property
    def current_option(self) -> str:
        """Return current lock mode."""
        return self.coordinator.lock_mode

    async def async_select_option(self, option: str) -> None:
        """Change the lock mode."""
        await self.coordinator.async_set_lock_mode(option)
```

### 9. Binary Sensor (`binary_sensor.py`)

**Add lock active sensor:**

```python
# Add to async_setup_entry:
entities = [
    # ... existing sensors ...
    LockActiveSensor(coordinator),
]

class LockActiveSensor(IntegrationBinarySensor):
    """Binary sensor indicating if cover lock is active."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(
            coordinator,
            BinarySensorEntityDescription(
                key=const.SENSOR_KEY_LOCK_ACTIVE,
                name="Lock Active",
                icon="mdi:lock",
                device_class=BinarySensorDeviceClass.LOCK,
            ),
        )

    @property
    def is_on(self) -> bool:
        """Return True if lock is active."""
        return self.coordinator.is_locked
```

### 10. Regular Sensor (`sensor.py`)

**Add lock mode state sensor:**

```python
# Add to async_setup_entry:
entities = [
    # ... existing sensors ...
    LockModeSensor(coordinator),
]

class LockModeSensor(IntegrationSensor):
    """Sensor showing current lock mode."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(
            coordinator,
            SensorEntityDescription(
                key=SELECT_KEY_LOCK_MODE,
                name="Lock Mode State",
                icon="mdi:lock-outline",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        )

    @property
    def native_value(self) -> str:
        """Return current lock mode."""
        return self.coordinator.lock_mode
```

### 11. Manifest Update (`manifest.json`)

**Update dependencies if needed:**
```json
{
  "dependencies": [
    "logbook",
    "sun",
    "weather"
  ]
}
```
(No changes needed - select platform is built-in)

### 12. Translations (`strings.json`)

**Add translations:**

```json
{
  "entity": {
    "select": {
      "lock_mode": {
        "name": "Lock Mode",
        "state": {
          "unlocked": "Unlocked (automation active)",
          "hold_position": "Hold current position",
          "force_open": "Force open and lock",
          "force_close": "Force close and lock"
        }
      }
    },
    "binary_sensor": {
      "lock_active": {
        "name": "Lock Active"
      }
    },
    "sensor": {
      "lock_mode_state": {
        "name": "Lock Mode State"
      }
    }
  },
  "services": {
    "set_lock": {
      "name": "Set Cover Lock",
      "description": "Lock all covers in a specific state",
      "fields": {
        "lock_mode": {
          "name": "Lock Mode",
          "description": "How to lock the covers"
        }
      }
    }
  }
}
```

## Implementation Order

1. **Phase 1: Core Infrastructure**
   - [ ] Update `const.py` with new constants
   - [ ] Update `config.py` with lock mode config key
   - [ ] Add lock state management to `coordinator.py`
   - [ ] Create `services.yaml`

2. **Phase 2: Logic Implementation**
   - [ ] Modify `automation_engine.py` to pass lock mode
   - [ ] Modify `cover_automation.py` to handle lock modes
   - [ ] Update service registration in `__init__.py`

3. **Phase 3: UI Components**
   - [ ] Create `select.py` with LockModeSelect entity
   - [ ] Add LockActiveSensor to `binary_sensor.py`
   - [ ] Add LockModeSensor to `sensor.py`

4. **Phase 4: Testing & Documentation**
   - [ ] Update translations in `strings.json`
   - [ ] Write unit tests for lock logic
   - [ ] Write integration tests for service
   - [ ] Update documentation

## Testing Strategy

### Unit Tests

1. **Lock Mode State Management** (`test_coordinator_lock.py`)
   - Test `async_set_lock_mode()` updates state
   - Test state persistence to config
   - Test coordinator refresh trigger

2. **Cover Automation Lock Logic** (`test_cover_automation_lock.py`)
   - Test HOLD_POSITION blocks all movement
   - Test FORCE_OPEN moves cover to 100%
   - Test FORCE_CLOSE moves cover to 0%
   - Test cover already at target position (no movement)
   - Test moving cover is skipped (let it finish)

3. **Service Tests** (`test_service_set_lock.py`)
   - Test service call with valid lock modes
   - Test service call with invalid lock mode
   - Test service updates coordinator state

### Integration Tests

1. **End-to-End Lock Scenarios** (`test_lock_scenarios.py`)
   - Test hail protection: force_close → all covers close → hold
   - Test manual override: hold_position → user opens cover manually → stays open
   - Test unlock: covers resume normal automation

## Example Usage

### Automation: Hail Protection
```yaml
automation:
  - alias: "Hail Protection - Close Covers"
    trigger:
      - platform: state
        entity_id: binary_sensor.hail_warning
        to: 'on'
    action:
      - service: smart_cover_automation.set_lock
        data:
          lock_mode: force_close
      - service: notify.mobile_app
        data:
          message: "Hail warning! Closing and locking all covers."

  - alias: "Hail Protection - Resume Automation"
    trigger:
      - platform: state
        entity_id: binary_sensor.hail_warning
        to: 'off'
        for:
          minutes: 30
    action:
      - service: smart_cover_automation.set_lock
        data:
          lock_mode: unlocked
      - service: notify.mobile_app
        data:
          message: "Hail warning cleared. Resuming normal automation."
```

### Manual Control via Select Entity
```yaml
# In Lovelace UI
type: entities
entities:
  - entity: select.smart_cover_automation_lock_mode
  - entity: binary_sensor.smart_cover_automation_lock_active
```

### Script: Manual Hold
```yaml
script:
  hold_covers_for_cleaning:
    alias: "Hold Covers While Cleaning"
    sequence:
      - service: smart_cover_automation.set_lock
        data:
          lock_mode: hold_position
      - delay:
          hours: 2
      - service: smart_cover_automation.set_lock
        data:
          lock_mode: unlocked
```

## Key Design Decisions

### 1. Global vs Per-Cover Lock
**Decision:** Global lock (affects all covers)
**Rationale:**
- Simpler implementation
- Matches use case (hail affects all windows)
- Can be extended to per-cover later if needed

### 2. Let Movements Finish
**Decision:** Skip covers that are currently moving
**Rationale:**
- Safer (don't interrupt motor operations)
- Simpler logic (no need to track interrupted movements)
- Checked at start of `process()` method

### 3. Re-evaluate Every Run
**Decision:** Process locked covers in each automation cycle
**Rationale:**
- Ensures covers reach target position even if manually moved
- Example: FORCE_OPEN → user manually closes → next cycle reopens
- Maintains consistent state enforcement

### 4. Service + Select Entity
**Decision:** Both interfaces available
**Rationale:**
- Service: Best for automations (flexible, scriptable)
- Select: Best for manual control (visual, easy to use)
- Both modify same coordinator state (single source of truth)

### 5. No Timeout
**Decision:** Manual unlock required
**Rationale:**
- Safety: Don't auto-unlock during weather emergency
- User control: Explicit unlock action required
- Can be added via automation if desired (user's choice)

## Migration & Compatibility

### Config Entry Migration
- Add default `lock_mode: unlocked` to existing installations
- No breaking changes to existing configuration
- Backward compatible

### State Preservation
- Lock state persists across HA restarts
- Stored in config entry options
- Coordinator reads on initialization

## Performance Considerations

- Lock check is O(1) operation (simple string comparison)
- No additional API calls introduced
- Minimal overhead on automation cycle
- Position history still maintained while locked

## Error Handling

1. **Invalid Lock Mode**: Log error, ignore service call
2. **Cover Unavailable**: Skip cover (existing behavior)
3. **Movement Failure**: Log error, try next cycle
4. **Service Call Failure**: Return error to caller

## Success Criteria

- ✅ Service `set_lock` changes coordinator state
- ✅ Select entity reflects current lock mode
- ✅ HOLD_POSITION blocks all automation
- ✅ FORCE_OPEN moves covers to 100%
- ✅ FORCE_CLOSE moves covers to 0%
- ✅ Covers re-evaluated each cycle while locked
- ✅ Moving covers are not interrupted
- ✅ Lock state persists across restarts
- ✅ All tests pass (unit + integration)
- ✅ Documentation complete
